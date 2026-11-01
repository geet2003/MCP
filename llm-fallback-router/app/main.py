
import hashlib

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.database import initialize_database
from app.rate_limiter import (
    reserve_tokens,
    estimate_tokens,
    RateLimitExceeded
)
from app.router import route_request, GatewayError


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()
    yield


app = FastAPI(
    title="LLM Gateway Fallback Router",
    description="Token-aware rate limiting and model fallback",
    lifespan=lifespan
)


class CompletionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100000)
    max_tokens: int = Field(default=1000, ge=1, le=50000)

    # Used only for local mock-provider testing.
    scenario: str = Field(
        default="success",
        pattern="^(success|429|timeout|error)$"
    )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "database": "sqlite",
        "provider": "mock"
    }


@app.post("/api/complete")
async def complete(
    request: CompletionRequest,
    x_api_key: str = Header(default=None)
):

    # Demo authentication.
    if not x_api_key or len(x_api_key) < 8:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "A valid API key is required."
                }
            }
        )

    # Hash API keys rather than storing raw keys in SQLite.
    tenant_id = hashlib.sha256(
        x_api_key.encode()
    ).hexdigest()

    # Reserve prompt tokens + requested completion budget.
    requested_tokens = (
        estimate_tokens(request.prompt)
        + request.max_tokens
    )

    try:
        usage = await reserve_tokens(
            tenant_id,
            requested_tokens
        )

    except RateLimitExceeded as error:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Tenant token limit exceeded.",
                    "limit": 50000,
                    "used": error.used,
                    "requested": error.requested
                }
            },
            headers={
                "Retry-After": "60"
            }
        )

    try:
        result = await route_request(
            request.prompt,
            request.scenario
        )

        return {
            "success": True,
            "data": result,
            "usage": {
                "reserved_tokens": requested_tokens,
                "remaining_tokens": usage["remaining"]
            }
        }

    except GatewayError as error:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message
                }
            }
        )

    except Exception:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "GATEWAY_INTERNAL_ERROR",
                    "message": "An unexpected gateway error occurred."
                }
            }
        )
