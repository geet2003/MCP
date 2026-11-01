
import os
import aiosqlite

from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "./gateway.db"
)


async def initialize_database():

    async with aiosqlite.connect(DATABASE_PATH) as db:

        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                created_at REAL NOT NULL
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_time
            ON token_usage(tenant_id, created_at)
        """)

        await db.commit()
