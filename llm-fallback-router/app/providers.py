
import asyncio


class ProviderRateLimitError(Exception):
    pass


class ProviderError(Exception):
    pass


async def primary_provider(prompt, scenario="success"):

    print("Calling PRIMARY provider...")

    if scenario == "429":
        raise ProviderRateLimitError()

    if scenario == "timeout":
        await asyncio.sleep(5)

    if scenario == "error":
        raise ProviderError("Internal primary provider failure")

    await asyncio.sleep(0.2)

    return {
        "provider": "primary",
        "model": "mock-gpt-primary",
        "content": f"Primary model response for: {prompt}"
    }


async def backup_provider(prompt):

    print("Calling BACKUP provider...")

    await asyncio.sleep(0.2)

    return {
        "provider": "backup",
        "model": "mock-gpt-backup",
        "content": f"Backup model response for: {prompt}"
    }

