
import os
import time
import math
import aiosqlite

from dotenv import load_dotenv
from app.database import DATABASE_PATH

load_dotenv()

TOKEN_LIMIT = int(os.getenv("TOKEN_LIMIT", 50000))
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", 60))


class RateLimitExceeded(Exception):
    def __init__(self, used, requested):
        self.used = used
        self.requested = requested
        super().__init__("Tenant token limit exceeded")


def estimate_tokens(text: str) -> int:
    """
    Simple mock token estimator.

    For production, use the tokenizer corresponding
    to the selected model.
    """
    return max(1, math.ceil(len(text) / 4))


async def reserve_tokens(tenant_id: str, tokens: int):

    if tokens <= 0 or tokens > TOKEN_LIMIT:
        raise RateLimitExceeded(0, tokens)

    now = time.time()
    window_start = now - WINDOW_SECONDS

    async with aiosqlite.connect(DATABASE_PATH) as db:

        await db.execute("PRAGMA busy_timeout = 5000")

        # Serialize competing quota reservations.
        await db.execute("BEGIN IMMEDIATE")

        try:
            # Remove expired usage.
            await db.execute("""
                DELETE FROM token_usage
                WHERE created_at <= ?
            """, (window_start,))

            # Calculate current tenant consumption.
            cursor = await db.execute("""
                SELECT COALESCE(SUM(tokens), 0)
                FROM token_usage
                WHERE tenant_id = ?
                AND created_at > ?
            """, (tenant_id, window_start))

            row = await cursor.fetchone()

            used = row[0] or 0

            if used + tokens > TOKEN_LIMIT:

                raise RateLimitExceeded(
                    used,
                    tokens
                )

            # Reserve capacity before contacting provider.
            await db.execute("""
                INSERT INTO token_usage (
                    tenant_id,
                    tokens,
                    created_at
                )
                VALUES (?, ?, ?)
            """, (tenant_id, tokens, now))

            await db.commit()

            return {
                "used": used + tokens,
                "remaining": TOKEN_LIMIT - used - tokens
            }

        except Exception:
            await db.rollback()
            raise
