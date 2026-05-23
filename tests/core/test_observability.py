"""Structured trace sink registration."""

from unittest.mock import MagicMock, patch

from core import observability
from core.trace import trace_event


def _trace_settings(**kwargs):
    from types import SimpleNamespace

    base = {
        "structured_trace_sink": "default",
        "otlp_exporter_endpoint": None,
        "otlp_exporter_service_name": "free-claude-code",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_trace_event_dispatches_via_observability_hook() -> None:
    sink = MagicMock()
    observability.set_trace_dispatch(sink)
    try:
        trace_event(stage="ingress", event="probe.e", source="test", foo=42)
        sink.assert_called_once()
        payload = sink.call_args[0][0]
        assert payload["stage"] == "ingress"
        assert payload["event"] == "probe.e"
        assert payload["source"] == "test"
        assert payload["foo"] == 42
    finally:
        observability.set_trace_dispatch(None)


def test_structured_trace_noop_replaces_active_sink() -> None:
    """``STRUCTURED_TRACE_SINK=noop`` must not forward to a previously installed sink."""

    from api.trace_sink import (
        apply_structured_trace_settings,
        reset_structured_trace_settings,
    )

    prior = MagicMock()
    observability.set_trace_dispatch(prior)
    prior.reset_mock()
    try:
        apply_structured_trace_settings(_trace_settings(structured_trace_sink="noop"))
        trace_event(stage="ingress", event="after.noop", source="test")
        prior.assert_not_called()
    finally:
        reset_structured_trace_settings()


def test_structured_trace_default_restores_builtin_dispatch() -> None:
    """``default`` clears custom dispatch so :func:`dispatch_structured_trace` uses built-ins."""

    from api.trace_sink import apply_structured_trace_settings

    with (
        patch("api.telemetry_otlp.shutdown_otlp_tracer_provider"),
        patch("api.trace_sink.set_trace_dispatch") as set_dispatch,
    ):
        apply_structured_trace_settings(
            _trace_settings(structured_trace_sink="default")
        )
    set_dispatch.assert_called_once_with(None)


def test_structured_trace_otlp_http_registers_otlp_sink() -> None:
    """``otlp_http`` wires OTLP dispatcher from settings (mocked exporter stack)."""

    from api.trace_sink import (
        apply_structured_trace_settings,
        reset_structured_trace_settings,
    )

    fake_sink = MagicMock()

    try:
        with (
            patch("api.telemetry_otlp.shutdown_otlp_tracer_provider"),
            patch(
                "api.telemetry_otlp.build_structured_trace_otlp_sink",
                return_value=fake_sink,
            ) as build_otlp,
            patch("api.trace_sink.set_trace_dispatch") as set_dispatch,
        ):
            apply_structured_trace_settings(
                _trace_settings(
                    structured_trace_sink="otlp_http",
                    otlp_exporter_endpoint=" https://collector.test/v1/traces ",
                    otlp_exporter_service_name=" svc-test ",
                )
            )
        build_otlp.assert_called_once_with(
            endpoint="https://collector.test/v1/traces",
            service_name="svc-test",
        )
        set_dispatch.assert_called_once_with(fake_sink)
    finally:
        reset_structured_trace_settings()


def test_reset_structured_trace_shuts_down_otlp() -> None:
    """Reset clears OTLP provider state before restoring built-ins."""

    from api.trace_sink import reset_structured_trace_settings

    with patch("api.telemetry_otlp.shutdown_otlp_tracer_provider") as shutdown:
        reset_structured_trace_settings()
    shutdown.assert_called_once()
