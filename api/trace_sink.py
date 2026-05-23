"""Wire structured trace dispatch from typed settings (:mod:`core` stays config-free).

``core.observability`` exposes :func:`~core.observability.set_trace_dispatch`; this module
consumes typed settings exposing ``structured_trace_sink`` (:class:`~config.settings.Settings`).
"""

from __future__ import annotations

from typing import Any, Protocol

from config.observability_settings import StructuredTraceSink
from core.observability import set_trace_dispatch


class StructuredTraceSinkSource(Protocol):
    structured_trace_sink: StructuredTraceSink
    otlp_exporter_endpoint: str | None
    otlp_exporter_service_name: str


def reset_structured_trace_settings() -> None:
    """Restore built-in structured trace emission (clear any custom dispatch)."""

    from api.telemetry_otlp import shutdown_otlp_tracer_provider

    shutdown_otlp_tracer_provider()
    set_trace_dispatch(None)


def apply_structured_trace_settings(settings: StructuredTraceSinkSource) -> None:
    """Install ``noop``, OTLP dispatch, or revert to defaults per ``structured_trace_sink``."""

    from api.telemetry_otlp import (
        build_structured_trace_otlp_sink,
        shutdown_otlp_tracer_provider,
    )

    shutdown_otlp_tracer_provider()

    mode: StructuredTraceSink = settings.structured_trace_sink
    if mode == "noop":

        def _discard(_payload: dict[str, Any]) -> None:
            return None

        set_trace_dispatch(_discard)
        return

    if mode == "default":
        set_trace_dispatch(None)
        return

    if mode == "otlp_http":
        endpoint = (settings.otlp_exporter_endpoint or "").strip()
        service = (settings.otlp_exporter_service_name or "free-claude-code").strip()
        sink = build_structured_trace_otlp_sink(endpoint=endpoint, service_name=service)
        set_trace_dispatch(sink)
        return

    msg = f"unknown structured_trace_sink: {mode!r}"
    raise ValueError(msg)
