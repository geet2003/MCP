import asyncio
import json
import sys
from pydantic import BaseModel, Field, ValidationError
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

# ==========================================
# 1. Strict Schema Definitions (Pydantic V2)
# ==========================================

class GetCustomerRecordArgs(BaseModel):
    customer_id: str = Field(
        ..., 
        pattern=r"^CUST-[A-Z0-9]{5}$",
        description="Customer ID formatted as CUST-XXXXX where XXXXX is 5 alphanumeric characters."
    )

class TriggerRefundArgs(BaseModel):
    customer_id: str = Field(
        ..., 
        pattern=r"^CUST-[A-Z0-9]{5}$",
        description="Customer ID formatted as CUST-XXXXX."
    )
    amount: float = Field(
        ..., 
        gt=0, 
        description="Refund amount. Must be a positive floating-point number greater than 0."
    )
    reason: str = Field(
        ..., 
        min_length=10, 
        description="Detailed reason for refund. Must be at least 10 characters long."
    )

# ==========================================
# 2. Server Initialization & Capabilities
# ==========================================

server = Server("customer-service-mcp")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Exposes tool definitions with strict JSON schemas pulled from Pydantic models."""
    return [
        types.Tool(
            name="get_customer_record",
            description="Retrieve customer profile and account details by customer ID.",
            inputSchema=GetCustomerRecordArgs.model_json_schema(),
        ),
        types.Tool(
            name="trigger_refund",
            description="Process a financial refund for a customer. Requires valid ID, positive amount, and detailed reason.",
            inputSchema=TriggerRefundArgs.model_json_schema(),
        ),
    ]

# ==========================================
# 3. Tool Execution & Error Interception
# ==========================================

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Executes tools and converts schema validation failures into standard JSON-RPC codes."""
    if not arguments:
        arguments = {}

    # --- Tool 1 Execution ---
    if name == "get_customer_record":
        try:
            validated_args = GetCustomerRecordArgs(**arguments)
        except ValidationError as e:
            # INTERCEPTION: Convert Pydantic error into standard JSON-RPC Invalid Params (-32602)
            raise types.McpError(
                code=types.INVALID_PARAMS,
                message=f"Invalid params: {str(e)}"
            )

        customer_id = validated_args.customer_id
        print(f"[DEBUG] Successfully retrieved record for {customer_id}", file=sys.stderr)
        
        record = {
            "customer_id": customer_id,
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "account_status": "Active",
            "tier": "Premium"
        }
        return [types.TextContent(type="text", text=json.dumps(record))]

    # --- Tool 2 Execution ---
    elif name == "trigger_refund":
        try:
            validated_args = TriggerRefundArgs(**arguments)
        except ValidationError as e:
            # INTERCEPTION: Convert Pydantic error into standard JSON-RPC Invalid Params (-32602)
            raise types.McpError(
                code=types.INVALID_PARAMS,
                message=f"Invalid params: {str(e)}"
            )

        print(f"[DEBUG] Processing refund of {validated_args.amount} for {validated_args.customer_id}", file=sys.stderr)

        receipt = {
            "status": "SUCCESS",
            "transaction_id": "TXN-REF-987654",
            "customer_id": validated_args.customer_id,
            "refund_amount": validated_args.amount,
            "reason": validated_args.reason
        }
        return [types.TextContent(type="text", text=json.dumps(receipt))]

    else:
        # Standard fallback for missing tools
        raise types.McpError(
            code=types.METHOD_NOT_FOUND,
            message=f"Unknown tool: {name}"
        )

# ==========================================
# 4. Main Entrypoint & Transport Setup
# ==========================================

async def main():
    print("[INFO] Starting Customer Service Low-Level MCP Server on stdio transport...", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="customer-service-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
