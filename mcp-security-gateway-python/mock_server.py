from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock Downstream MCP Server")

@app.post("/mcp")
async def downstream_mcp(request: Request):
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": "get_customer_record", "description": "Fetch customer record"},
                    {"name": "admin_reset_key", "description": "Reset system API key"},
                ]
            }
        })

    if method == "tools/call":
        tool_name = params.get("name")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {"type": "text", "text": f"Successfully executed tool '{tool_name}'"}
                ]
            }
        })

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "Method not found"}
    })