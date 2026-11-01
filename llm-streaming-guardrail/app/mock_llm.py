
import asyncio


async def mock_llm_stream():

    # Simulated LLM output deliberately containing PII.
    response = (
        "Hello! Here is your information. "
        "Your email is john.doe@gmail.com. "
        "Your SSN is 123-45-6789. "
        "Your credit card number is 4111111111111111. "
        "Thank you!"
    )

    # Simulate streaming tokens.
    tokens = [
        "Hello! ",
        "Here is ",
        "your information. ",
        "Your email is ",
        "john.doe@",
        "gmail.com. ",
        "Your SSN is ",
        "123-",
        "45-6789. ",
        "Your credit card number is ",
        "4111111111111111. ",
        "Thank you!"
    ]

    for token in tokens:
        await asyncio.sleep(0.2)

        yield token
