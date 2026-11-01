import os
import logging
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
import httpx

# Configure logger to print to stderr/console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-gateway")

app = FastAPI(title="MCP Security Gateway Proxy")

DOWNSTREAM_MCP_URL = os.getenv("DOWNSTREAM_MCP_URL", "http://localhost:8080/mcp")


# ------------------------------------------------------------------
# Auth Context & RBAC Resolver
# ------------------------------------------------------------------
@dataclass
class UserContext:
    user_id: str
    role: str  # e.g., 'admin', 'viewer'


def authenticate_token(auth_header: Optional[str]) -> Optional[UserContext]:
    """Inspects the Bearer token and returns the authenticated user context."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1].strip()

    # Mock token resolution for assessment/testing purposes
    if token == "admin-secret-token":
        return UserContext(user_id="user-01", role="admin")
    elif token == "viewer-secret-token":
        return UserContext(user_id="user-02", role="viewer")

    return None


# ------------------------------------------------------------------
# JSON-RPC Helpers
# ------------------------------------------------------------------
def make_jsonrpc_error(
    req_id: Optional[Any], code: int, message: str
) -> Dict[str, Any]:
    """Formats a standard JSON-RPC 2.0 error response payload."""
    return {
        "jsonrpc": "2.0",
        "id": req_id if req_id is not None else None,
        "error": {
            "code": code,
            "message": message,
        },
    }


# ------------------------------------------------------------------
# MCP Gateway POST Endpoint
# ------------------------------------------------------------------
@app.post("/mcp")
async def mcp_gateway(request: Request) -> JSONResponse:
    # 1. Authenticate Request
    auth_header = request.headers.get("Authorization")
    user_context = authenticate_token(auth_header)

    # Note: Extract body parsing logic early to try and preserve client 'id' for errors
    try:
        json_rpc_body = await request.json()
    except Exception:
        json_rpc_body = {}

    req_id = json_rpc_body.get("id") if isinstance(json_rpc_body, dict) else None

    if not user_context:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=make_jsonrpc_error(
                req_id, -32000, "Authentication failed: Invalid or missing Bearer token"
            ),
        )

    # 2. Validate JSON-RPC Structural Basics
    if (
        not isinstance(json_rpc_body, dict)
        or json_rpc_body.get("jsonrpc") != "2.0"
        or "method" not in json_rpc_body
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=make_jsonrpc_error(
                req_id, -32600, "Invalid Request: Not a valid JSON-RPC 2.0 object"
            ),
        )

    method = json_rpc_body.get("method")
    params = json_rpc_body.get("params", {})

    # 3. Method & Tool Inspection (Authorization Logic)
    if method == "tools/call":
        tool_name = params.get("name") if isinstance(params, dict) else None

        if not tool_name or not isinstance(tool_name, str):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=make_jsonrpc_error(
                    req_id, -32602, "Invalid params: tool name missing in tools/call"
                ),
            )

        # Rule: Admin tools (e.g. starting with "admin_") require 'admin' role
        if tool_name.startswith("admin_") and user_context.role != "admin":
            logger.warning(
                f"[INTERCEPTED] User '{user_context.user_id}' ({user_context.role}) "
                f"attempted to invoke restricted tool '{tool_name}'"
            )

            # Return direct JSON-RPC error (-32001) without forwarding downstream
            return JSONResponse(
                status_code=status.HTTP_200_OK,  # Standard JSON-RPC protocol error over HTTP 200
                content=make_jsonrpc_error(
                    req_id,
                    -32001,
                    f"Unauthorized Tool Call: Role '{user_context.role}' is not allowed to call tool '{tool_name}'",
                ),
            )

    # 4. Forward Authorized Requests to Downstream MCP Server
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            downstream_response = await client.post(
                DOWNSTREAM_MCP_URL,
                json=json_rpc_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Authenticated-User": user_context.user_id,
                    "X-Authenticated-Role": user_context.role,
                },
            )

            return JSONResponse(
                status_code=downstream_response.status_code,
                content=downstream_response.json(),
            )
        except httpx.RequestError as exc:
            logger.error(f"[GATEWAY ERROR] Downstream forward failed: {exc}")
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content=make_jsonrpc_error(
                    req_id, -32603, "Internal Error: Unable to reach downstream MCP server"
                ),
            )