"""
SQLite database for storing audits, users, and API usage tracking.
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import asyncio
import aiosqlite
from pathlib import Path

DATABASE_PATH = os.getenv("DATABASE_PATH", "audits.db")


def get_db_path() -> str:
    """Get the database file path."""
    return str(Path(__file__).parent.parent / DATABASE_PATH)


@contextmanager
def get_db_connection():
    """Synchronous database connection context manager."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


async def get_async_db():
    """Get async database connection."""
    return await aiosqlite.connect(get_db_path())


def init_database():
    """Initialize database with required tables."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Audits table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id TEXT PRIMARY KEY,
                business_name TEXT NOT NULL,
                website_url TEXT,
                industry TEXT,
                location TEXT,
                input_data TEXT NOT NULL,
                audit_result TEXT NOT NULL,
                overall_score INTEGER,
                grade TEXT,
                is_paid INTEGER DEFAULT 0,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table (for paid customers)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                stripe_customer_id TEXT,
                whop_user_id TEXT
            )
        ''')
        
        # API usage tracking for rate limiting
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                audit_id TEXT,
                FOREIGN KEY (audit_id) REFERENCES audits (id)
            )
        ''')
        
        # Payments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                audit_id TEXT NOT NULL,
                email TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'pending',
                provider TEXT DEFAULT 'whop',
                provider_payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (audit_id) REFERENCES audits (id)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audits_email ON audits(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audits_business ON audits(business_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_ip ON api_usage(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp)')
        
        conn.commit()


async def save_audit(
    audit_id: str,
    business_name: str,
    input_data: dict,
    audit_result: dict,
    website_url: Optional[str] = None,
    industry: Optional[str] = None,
    location: Optional[str] = None,
    email: Optional[str] = None,
    is_test: bool = False
) -> str:
    """
    Save an audit result to the database.
    
    Args:
        audit_id: Unique ID for this audit
        business_name: Name of the business
        input_data: Original input data
        audit_result: Full audit result from Groq
        website_url: Business website
        industry: Business industry
        location: Business location
        email: Email to send report to
        is_test: Whether this is a test audit
        
    Returns:
        The audit ID
    """
    # Add test flag to audit result metadata
    if is_test:
        if '_metadata' not in audit_result:
            audit_result['_metadata'] = {}
        audit_result['_metadata']['isTest'] = True
    
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute('''
            INSERT INTO audits (
                id, business_name, website_url, industry, location,
                input_data, audit_result, overall_score, grade, email
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            audit_id,
            business_name,
            website_url,
            industry,
            location,
            json.dumps(input_data),
            json.dumps(audit_result),
            audit_result.get('overallScore', 0),
            audit_result.get('grade', 'F'),
            email
        ))
        await db.commit()
    
    return audit_id


async def get_audit_by_id(audit_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve an audit by ID.
    
    Args:
        audit_id: The audit ID
        
    Returns:
        Audit data or None if not found
    """
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM audits WHERE id = ?',
            (audit_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'business_name': row['business_name'],
                    'website_url': row['website_url'],
                    'industry': row['industry'],
                    'location': row['location'],
                    'input_data': json.loads(row['input_data']),
                    'audit_result': json.loads(row['audit_result']),
                    'overall_score': row['overall_score'],
                    'grade': row['grade'],
                    'is_paid': bool(row['is_paid']),
                    'email': row['email'],
                    'created_at': row['created_at'],
                }
    return None


async def mark_audit_paid(audit_id: str, payment_id: Optional[str] = None) -> bool:
    """Mark an audit as paid."""
    async with aiosqlite.connect(get_db_path()) as db:
        cursor = await db.execute(
            'UPDATE audits SET is_paid = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (audit_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def track_api_usage(ip_address: str, endpoint: str, audit_id: Optional[str] = None):
    """Track API usage for rate limiting."""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            'INSERT INTO api_usage (ip_address, endpoint, audit_id) VALUES (?, ?, ?)',
            (ip_address, endpoint, audit_id)
        )
        await db.commit()


async def check_rate_limit(ip_address: str, limit: int = 10, window_hours: int = 1) -> tuple[bool, int]:
    """
    Check if an IP is within rate limits.
    
    Args:
        ip_address: Client IP address
        limit: Max requests allowed
        window_hours: Time window in hours
        
    Returns:
        Tuple of (is_allowed, remaining_requests)
    """
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)
    
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute(
            '''SELECT COUNT(*) as count FROM api_usage 
               WHERE ip_address = ? AND timestamp > ?''',
            (ip_address, cutoff.isoformat())
        ) as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0
    
    remaining = max(0, limit - count)
    is_allowed = count < limit
    
    return is_allowed, remaining


async def save_payment(
    payment_id: str,
    audit_id: str,
    email: str,
    amount: float,
    provider: str = "whop",
    provider_payment_id: Optional[str] = None
) -> str:
    """Save a payment record."""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute('''
            INSERT INTO payments (id, audit_id, email, amount, provider, provider_payment_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (payment_id, audit_id, email, amount, provider, provider_payment_id))
        await db.commit()
    return payment_id


async def complete_payment(payment_id: str) -> bool:
    """Mark a payment as completed."""
    async with aiosqlite.connect(get_db_path()) as db:
        cursor = await db.execute('''
            UPDATE payments 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (payment_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_recent_audits(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent audits for admin dashboard."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT id, business_name, overall_score, grade, created_at FROM audits ORDER BY created_at DESC LIMIT ?',
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# Initialize database on module load
init_database()
