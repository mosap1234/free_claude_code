# Deferred architecture milestones

Work intentionally **not** bundled with the consolidated roadmap implementation. Track these as separate issues or release milestones.

| Item | Reference |
|------|-----------|
| Native Anthropic HTTP adapter collapse | [providers/notes/native_anthropic_http_providers.md](../../providers/notes/native_anthropic_http_providers.md), IMPROVEMENT_PLAN Phase 3b |
| Observability port (trace backend abstraction) | Pluggable sink entrypoint [`core/observability.py`](../../core/observability.py) + [`core/trace.py`](../../core/trace.py); OTLP/backend wiring still backlog |
| `Depends(get_settings)` inside global exception handlers | FastAPI limitation; prefer explicit `get_settings()` in handlers (documented in IMPROVEMENT_PLAN Phase 5) |
| Packaging `smoke` in the wheel | Intentionally dev-only per IMPROVEMENT_PLAN |
| Further slim `config/settings.py` | Mixins exist; additional thin-down is optional (see [STATUS.md](STATUS.md)) |
| `PlatformOutbound` protocol for messaging | [messaging.md](messaging.md) optional future work |
