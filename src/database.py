"""
SQLite database for API usage tracking and rate limiting.
All audit and user data is now stored in Supabase.
"""
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager
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


def init_database():
    """Initialize database with required tables for rate limiting."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # API usage tracking for rate limiting (Persistence kept in SQLite for performance/simplicity)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                audit_id TEXT
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_ip ON api_usage(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp)')
        
        conn.commit()


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


# Initialize database on module load
init_database()
