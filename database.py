
import os
import asyncio
from fastapi import Request
import asyncpg

# Explicitly using your Neon connection string
# Production Tip: In the future, you can read this via os.getenv("DATABASE_URL")
DATABASE_URL = "postgresql://neondb_owner:npg_rCJwoG8xylv7@ep-dark-poetry-anz1nhcq-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

class DatabaseManager:
    def __init__(self):
        self.pool: asyncpg.Pool = None

    async def connect(self):
        """Initializes the connection pool."""
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=2,      # Minimum active connections to keep open
                    max_size=10,     # Maximum connections inside your pooler limits
                    timeout=30.0,    # Connection timeout thresholds
                    command_timeout=60.0,
                    statement_cache_size=0
                )
                print(" Successfully connected to Neon PostgreSQL Pool.")
            except Exception as e:
                print(f" Failed to initialize Neon Connection Pool: {e}")
                raise e

    async def disconnect(self):
        """Gracefully closes all pool connections."""
        if self.pool:
            await self.pool.close()
            print(" Neon PostgreSQL Pool connections released safely.")

db_manager = DatabaseManager()

# FastAPI Dependency injection provider
async def get_db(request: Request):
    """
    Yields a connection from the global application pool.
    Automatically releases the connection back to the pool when the request finishes.
    """
    # Pulls the pool context safely directly from the stateful app middleware runtime
    pool = request.app.state.db_pool
    async with pool.acquire() as connection:
        yield connection