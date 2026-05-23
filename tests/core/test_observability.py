"""Structured trace sink registration."""

from __future__ import annotations

from unittest.mock import MagicMock

from core import observability
from core.trace import trace_event


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
