# AI Field Developer Assessment — MCP & LLM Gateway Tasks

Four practical implementations covering MCP servers, security proxy gateways, LLM streaming guardrails, and model fallback routing.

---

## Project Structure

```
MCP/
├── mcp-customer-server/         # Task 1 — MCP Server with strict validation
├── mcp-security-gateway-python/ # Task 2 — MCP Security Gateway Proxy
├── llm-streaming-guardrail/     # Task 3 — LLM Streaming PII Redaction
└── llm-fallback-router/         # Task 4 — Rate Limiting & Model Fallback Router
```

---

## Task 1 — Custom MCP Server (`mcp-customer-server/`)

MCP server exposing two tools over stdio transport with strict Pydantic V2 validation.

**Tools:**
- `get_customer_record` — accepts `customer_id` matching `CUST-XXXXX`
- `trigger_refund` — accepts `customer_id`, positive `amount`, and `reason` (min 10 chars)

Invalid inputs are rejected with standard JSON-RPC error code `-32602`.
All debug output is written exclusively to `stderr`; `stdout` is reserved for JSON-RPC messages.

**Setup & Run:**
```bash
cd mcp-customer-server
pip install -r requirements.txt
python server.py
```

---

## Task 2 — MCP Security Gateway Proxy (`mcp-security-gateway-python/`)

HTTP/JSON-RPC reverse proxy that enforces role-based access control before forwarding to a downstream MCP server.

**Behaviour:**
- Reads `Authorization: Bearer <token>` and resolves the caller's role (`admin` or `viewer`)
- `tools/list` — forwarded transparently to the downstream server
- `tools/call` with a tool name prefixed `admin_` — requires `admin` role; otherwise intercepted and returns JSON-RPC error `-32001` (Unauthorized Tool Call) without touching the downstream server

**Test tokens:**
| Token | Role |
|---|---|
| `admin-secret-token` | admin |
| `viewer-secret-token` | viewer |

**Setup & Run:**

Terminal 1 — start the mock downstream server:
```bash
cd mcp-security-gateway-python
pip install -r requirements.txt
uvicorn mock_server:app --port 8080
```

Terminal 2 — start the gateway:
```bash
uvicorn gateway:app --port 8000
```

**Example requests:**
```bash
# Allowed — viewer listing tools
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer viewer-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Blocked — viewer attempting admin tool
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer viewer-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"admin_reset_key"}}'

# Allowed — admin calling admin tool
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer admin-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"admin_reset_key"}}'
```

---

## Task 3 — LLM Streaming Guardrail (`llm-streaming-guardrail/`)

FastAPI gateway that proxies LLM text generation and redacts PII from the response stream in real time.

**Redacted patterns:**
- Email addresses
- Social Security Numbers (`XXX-XX-XXXX`)
- Credit card numbers (validated with Luhn check)

Sensitive values are replaced with `[REDACTED]`. A sliding 260-character buffer ensures PII spanning chunk boundaries is caught without accumulating the full response in memory.

**Setup & Run:**
```bash
cd llm-streaming-guardrail
pip install -r requirements.txt
uvicorn app.main:app --port 8001
```

**Example request:**
```bash
curl -X POST http://localhost:8001/api/generate -N
```

The response streams as Server-Sent Events with PII redacted inline.

---

## Task 4 — Rate Limiting & Model Fallback Router (`llm-fallback-router/`)

Resilient LLM gateway with token-aware sliding window rate limiting and automatic provider failover, backed by on-disk SQLite.

**Features:**
- 50,000 tokens/minute per tenant API key (sliding window, persisted in SQLite with WAL mode)
- Tokens estimated from prompt length + `max_tokens` budget before the request is forwarded
- If the primary provider returns `429` or times out after 3000ms, the request is automatically retried against the backup provider
- All error responses are sanitized — no raw stack traces or internal details are leaked

**Setup & Run:**
```bash
cd llm-fallback-router
pip install -r requirements.txt
uvicorn app.main:app --port 8002
```

**Example requests:**
```bash
# Successful completion
curl -X POST http://localhost:8002/api/complete \
  -H "X-Api-Key: my-test-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello world", "max_tokens": 100, "scenario": "success"}'

# Trigger 429 fallback
curl -X POST http://localhost:8002/api/complete \
  -H "X-Api-Key: my-test-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello world", "max_tokens": 100, "scenario": "429"}'

# Trigger timeout fallback
curl -X POST http://localhost:8002/api/complete \
  -H "X-Api-Key: my-test-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello world", "max_tokens": 100, "scenario": "timeout"}'
```

**Scenarios:** `success` | `429` | `timeout` | `error`

---

## Requirements

All projects require Python 3.10+. Each folder contains its own `requirements.txt`:

```bash
pip install -r requirements.txt
```
