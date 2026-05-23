"""Logging verbosity and debug flags."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from .observability_settings import StructuredTraceSink


class ObservabilityMixin(BaseModel):
    log_raw_api_payloads: bool = Field(
        default=False, validation_alias="LOG_RAW_API_PAYLOADS"
    )
    log_raw_sse_events: bool = Field(
        default=False, validation_alias="LOG_RAW_SSE_EVENTS"
    )
    log_api_error_tracebacks: bool = Field(
        default=False, validation_alias="LOG_API_ERROR_TRACEBACKS"
    )
    log_raw_messaging_content: bool = Field(
        default=False, validation_alias="LOG_RAW_MESSAGING_CONTENT"
    )
    log_raw_cli_diagnostics: bool = Field(
        default=False, validation_alias="LOG_RAW_CLI_DIAGNOSTICS"
    )
    log_messaging_error_details: bool = Field(
        default=False, validation_alias="LOG_MESSAGING_ERROR_DETAILS"
    )
    debug_platform_edits: bool = Field(
        default=False, validation_alias="DEBUG_PLATFORM_EDITS"
    )
    debug_subagent_stack: bool = Field(
        default=False, validation_alias="DEBUG_SUBAGENT_STACK"
    )
    #: ``noop`` discards payloads from :func:`core.trace.trace_event` hook (default emits loguru).
    structured_trace_sink: StructuredTraceSink = Field(
        default="default", validation_alias="STRUCTURED_TRACE_SINK"
    )
    #: OTLP HTTP trace endpoint (typically ``…/v1/traces``) when ``STRUCTURED_TRACE_SINK=otlp_http``.
    otlp_exporter_endpoint: str | None = Field(
        default=None,
        validation_alias="FCC_OTLP_EXPORTER_ENDPOINT",
    )
    #: ``service.name`` resource value for OTLP spans.
    otlp_exporter_service_name: str = Field(
        default="free-claude-code",
        validation_alias="FCC_OTLP_SERVICE_NAME",
    )

    @model_validator(mode="after")
    def _otlp_requires_endpoint(self) -> Self:
        if self.structured_trace_sink != "otlp_http":
            return self
        if not (self.otlp_exporter_endpoint or "").strip():
            msg = (
                "structured_trace_sink=otlp_http requires FCC_OTLP_EXPORTER_ENDPOINT "
                "( OTLP HTTP /v1/traces URL )"
            )
            raise ValueError(msg)
        return self
