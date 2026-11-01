
from app.pii_redactor import StreamingPIIRedactor
from app.mock_llm import mock_llm_stream


async def stream_from_llm():

    redactor = StreamingPIIRedactor()

    async for token in mock_llm_stream():

        # Pass every incoming token through PII detection.
        safe_text = redactor.push(token)

        if safe_text:
            yield safe_text

    # Process remaining buffered content.
    remaining = redactor.flush()

    if remaining:
        yield remaining
