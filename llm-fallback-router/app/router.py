
import asyncio
import os

from dotenv import load_dotenv

from app.providers import (
    primary_provider,
    backup_provider,
    ProviderRateLimitError,
    ProviderError
)

load_dotenv()

PRIMARY_TIMEOUT = float(
    os.getenv("PRIMARY_TIMEOUT", 3.0)
)

BACKUP_TIMEOUT = float(
    os.getenv("BACKUP_TIMEOUT", 5.0)
)


class GatewayError(Exception):
    def __init__(self, code, message, status_code):
        self.code = code
        self.message = message
        self.status_code = status_code


async def route_request(prompt, scenario="success"):

    try:
        # Attempt primary model with a strict timeout.
        result = await asyncio.wait_for(
            primary_provider(prompt, scenario),
            timeout=PRIMARY_TIMEOUT
        )

        result["fallback_used"] = False

        return result

    except (ProviderRateLimitError, TimeoutError) as error:

        if isinstance(error, TimeoutError):
            print("Primary timeout. Switching to backup.")

        else:
            print("Primary returned 429. Switching to backup.")

        try:
            result = await asyncio.wait_for(
                backup_provider(prompt),
                timeout=BACKUP_TIMEOUT
            )

            result["fallback_used"] = True

            return result

        except Exception:
            raise GatewayError(
                "ALL_PROVIDERS_FAILED",
                "All model providers are currently unavailable.",
                503
            )

    except ProviderError:
        raise GatewayError(
            "PRIMARY_PROVIDER_ERROR",
            "The model provider could not process the request.",
            502
        )

    except Exception:
        raise GatewayError(
            "GATEWAY_INTERNAL_ERROR",
            "An unexpected gateway error occurred.",
            500
        )
