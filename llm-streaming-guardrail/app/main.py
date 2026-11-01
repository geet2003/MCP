
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.gateway import stream_from_llm


app = FastAPI(
    title="LLM Streaming Gateway",
    description="Mock LLM with PII Redaction"
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "provider": "mock-llm"
    }


@app.post("/api/generate")
async def generate():

    async def response_stream():

        async for text in stream_from_llm():

            yield (
                "data: "
                + json.dumps({"content": text})
                + "\n\n"
            )

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        response_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no"
        }
    )
