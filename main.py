"""
Business Digital Presence Audit API - Main Entry Point
"""
import os
import uvicorn
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables (check multiple locations)
env_paths = [
    Path(__file__).parent / "config" / ".env",
    Path(__file__).parent / ".env",
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()  # Try default .env from environment

# Import and initialize database
from src.database import init_database

def main():
    """Run the FastAPI server."""
    # Initialize database tables
    init_database()
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║     Business Digital Presence Audit API v2.0         ║
╠══════════════════════════════════════════════════════╣
║  Server starting at http://{host}:{port}              
║  Debug mode: {debug}                                  
║  API docs: http://{host}:{port}/docs                  
╚══════════════════════════════════════════════════════╝
    """)
    
    # Run server
    uvicorn.run(
        "src.api:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if debug else "warning"
    )


if __name__ == "__main__":
    main()
