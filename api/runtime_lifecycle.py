"""Shutdown helpers and startup logging shared by :class:`~api.runtime.AppRuntime`."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from config.settings import Settings
from providers.exceptions import ServiceUnavailableError

_SHUTDOWN_TIMEOUT_S = 5.0


async def best_effort(
    name: str,
    awaitable: Any,
    timeout_s: float = _SHUTDOWN_TIMEOUT_S,
    *,
    log_verbose_errors: bool = False,
) -> None:
    """Run a shutdown step with timeout; never raise to callers."""
    try:
        await asyncio.wait_for(awaitable, timeout=timeout_s)
    except TimeoutError:
        logger.warning("Shutdown step timed out: {} ({}s)", name, timeout_s)
    except Exception as e:
        if log_verbose_errors:
            logger.warning(
                "Shutdown step failed: {}: {}: {}",
                name,
                type(e).__name__,
                e,
            )
        else:
            logger.warning(
                "Shutdown step failed: {}: exc_type={}",
                name,
                type(e).__name__,
            )


def warn_if_process_auth_token(settings: Settings) -> None:
    """Warn when server auth was implicitly inherited from the shell."""
    if settings.uses_process_anthropic_auth_token():
        logger.warning(
            "ANTHROPIC_AUTH_TOKEN is set in the process environment but not in "
            "a configured .env file. The proxy will require that token. Add "
            "ANTHROPIC_AUTH_TOKEN= to .env to disable proxy auth, or set the "
            "same token in .env to make server auth explicit."
        )


def log_startup_failure(settings: Settings, exc: Exception) -> None:
    """Log startup failures without traceback noise unless verbose diagnostics are enabled."""
    message = startup_failure_message(settings, exc)
    logger.error("Startup failed:\n{}", message)


def startup_failure_message(settings: Settings, exc: Exception) -> str:
    """Return a concise startup failure message for logs and ASGI lifespan failure."""
    if isinstance(exc, ServiceUnavailableError):
        return exc.message.strip() or "Server startup failed."

    if settings.log_api_error_tracebacks:
        return f"{type(exc).__name__}: {exc}"

    return f"Server startup failed: exc_type={type(exc).__name__}"
