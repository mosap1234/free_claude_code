# Deferred architecture milestones

Work intentionally **not** bundled with the consolidated roadmap implementation. Track these as separate issues or release milestones.

| Item | Reference |
|------|-----------|
| Native Anthropic HTTP adapter collapse | In progress ([`providers/notes/native_anthropic_http_providers.md`](../../providers/notes/native_anthropic_http_providers.md)) — catalog feeds `ProviderConfig` stream/header profiles; shared [`oauth_bearer_model_list_headers`](../../providers/native_messages_support.py) for OpenAI-compatible model catalogs |
| Observability port (trace backend abstraction) | Mitigated: [`core/observability.dispatch_structured_trace`](../../core/observability.py) + [`trace_event`](../../core/trace.py); OTLP sink via **`STRUCTURED_TRACE_SINK`** / [`api/trace_sink.py`](../../api/trace_sink.py) with **`observability`** extra (`uv sync --extra observability`). Sampling / span taxonomy backlog |
| Global exception handlers + settings | Mitigated — [`api/app.py`](../../api/app.py) exception handlers call explicit [`get_settings()`](../../config/settings.py): `Depends(get_settings)` is not relied on inside those globals. FastAPI quirks remain vendor-side only. |
| Packaging `smoke` in the wheel | Out of scope for installs — Hatch packages stay `api`/`cli`/… only; reproducible tooling via **`dependency-groups.smoke`** in `pyproject.toml` (`uv sync --group smoke`) plus optional [`smoke-touch.yml`](../../.github/workflows/smoke-touch.yml) |
| Further slim `config/settings.py` | Mixins + [`settings_coherence_mixins.py`](../../config/settings_coherence_mixins.py); additional thin-down is optional (see [STATUS.md](STATUS.md)) |
| CI path-filtered jobs for `smoke/` | Optional hygiene workflow **[`.github/workflows/smoke-touch.yml`](../../.github/workflows/smoke-touch.yml)** fires on **`smoke/**`** PR edits (ruff + capability map). Not in default required-status set unless you intentionally add it. |
| `PlatformOutbound` protocol (messaging) | Done — [`messaging/platforms/outbound.py`](../../messaging/platforms/outbound.py); see [messaging.md](messaging.md). |
