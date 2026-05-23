"""Pluggable sinks for structured application telemetry without OTEL coupling.

:callable:`dispatch_structured_trace` is the choke point fed by :func:`core.trace.trace_event`.

Product layers may register an alternative backend at process startup via
:class:`set_trace_dispatch`; the default emits loguru TRACE rows unchanged.
"""

from collections.abc import Callable
from typing import Any

StructuredTraceSink = Callable[[dict[str, Any]], None]

_trace_sink: StructuredTraceSink | None = None


def set_trace_dispatch(sink: StructuredTraceSink | None) -> None:
    """Replace the trace sink globally (typically called once during app startup).

    Passing ``None`` restores the built-in loguru-backed sink used by defaults.
    """
    global _trace_sink
    _trace_sink = sink


def dispatch_structured_trace(payload: dict[str, Any]) -> None:
    """Deliver one sanitized TRACE payload according to the active sink."""

    if _trace_sink is not None:
        _trace_sink(payload)
        return

    from loguru import logger

    event = str(payload.get("event", ""))
    logger.bind(trace_payload=payload).info("TRACE {}", event)
