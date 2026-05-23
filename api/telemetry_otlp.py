"""Install OTLP-backed ``trace_event`` sinks (optional ``observability`` extra).

``core`` stays exporter-unaware — only this module constructs OpenTelemetry tracers.

See :mod:`api.trace_sink` for wiring from typed settings.

"""

import json
from collections.abc import Callable
from typing import Any

from loguru import logger

StructuredTraceCallable = Callable[[dict[str, Any]], None]

_bound_sdk_provider: Any = None


def shutdown_otlp_tracer_provider() -> None:
    """Flush and detach any SDK tracer provider we installed."""

    global _bound_sdk_provider

    tp = _bound_sdk_provider
    _bound_sdk_provider = None
    if tp is None:
        return
    flush = getattr(tp, "force_flush", None)
    if callable(flush):
        try:
            flush()
        except Exception as exc:
            logger.debug("OTLP tracer force_flush failed: {}", exc)
    shutdown_fn = getattr(tp, "shutdown", None)
    if callable(shutdown_fn):
        try:
            shutdown_fn()
        except Exception as exc:
            logger.debug("OTLP tracer shutdown failed: {}", exc)


def _coerce_otel_attribute_value(value: Any) -> str | bool | int | float | None:
    if value is None:
        return None
    if isinstance(value, bool | int | float):
        return value
    return str(value)[:8192]


def _payload_to_otel_span_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    """Map structured trace dicts onto primitive span attributes."""

    attrs: dict[str, Any] = {}
    for key in sorted(payload):
        val = payload[key]
        if isinstance(val, dict | list):
            try:
                raw = json.dumps(val, default=str)[:4096]
            except TypeError, ValueError:
                raw = str(val)[:4096]
            attrs[f"fcc.trace.{key}"] = raw
            continue
        coerced = _coerce_otel_attribute_value(val)
        if coerced is not None:
            attrs[f"fcc.trace.{key}"] = coerced
    return attrs


def build_structured_trace_otlp_sink(
    *,
    endpoint: str,
    service_name: str,
) -> StructuredTraceCallable:
    """Return a dispatcher that emits one span per :func:`~core.trace.trace_event` call."""

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        msg = (
            "structured_trace_sink=otlp_http requires optional dependencies; "
            "install with `uv sync --extra observability`"
        )
        raise ImportError(msg) from exc

    shutdown_otlp_tracer_provider()

    resource = Resource.create({"service.name": service_name.strip()})
    exporter = OTLPSpanExporter(endpoint=endpoint.strip())

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    global _bound_sdk_provider
    _bound_sdk_provider = tracer_provider

    trace.set_tracer_provider(tracer_provider)
    tracer = trace.get_tracer("fcc.structured_trace")

    def _sink(payload: dict[str, Any]) -> None:
        name = str(payload.get("event", "trace_event"))
        span = tracer.start_span(name)
        try:
            mapped = _payload_to_otel_span_attributes(dict(payload))
            for attr_key, attr_val in mapped.items():
                span.set_attribute(attr_key, attr_val)
        finally:
            span.end()

    return _sink
