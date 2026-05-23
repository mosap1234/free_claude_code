# Package layers

This repo is a layered Python layout. **Imports are enforced by** `tests/contracts/test_import_boundaries.py` — refactors must keep those tests green.

## Packages

| Package | Role |
|---------|------|
| `config` | Environment and provider catalog (`Settings`, `provider_catalog`). Must not import `api`, `messaging`, `cli`, `providers`, or `core`. |
| `core` | Neutral Anthropic protocol, SSE, and conversion helpers. Must not import product packages (`api`, `messaging`, `cli`, `providers`, `config`, `smoke`). |
| `providers` | Upstream adapters and `ProviderRegistry`. Must not import `api`, `messaging`, or `cli`. |
| `api` | FastHTTP layer, admin UI, orchestration wiring. Must only import a **narrow** `providers` facade (see contract test `_API_ALLOWED_PROVIDER_MODULES`). |
| `messaging` | Optional Discord/Telegram runtime. Wired from `AppRuntime`; must not import `api` or `cli`. Only `providers.nvidia_nim.transcription_backend` may be imported (`_MESSAGING_ALLOWED_PROVIDER_MODULES`). |
| `cli` | Entry points (`fcc-server`, etc.). May import only `api.app` / `api.admin_urls` plus non-API packages. |

## Provider resolution

1. **HTTP requests:** Use `resolve_provider(provider_type, app=request.app, settings=...)` from `api.dependencies`. The app-mounted `ProviderRegistry` lives at `app.state.provider_registry` after `AppRuntime.startup`.

2. **Scripts / unit tests without an app:** Use `get_process_cached_provider*` (legacy aliases still export `get_provider` / `get_provider_for_type`) backed by `api.provider_process_cache.PROCESS_PROVIDERS`.

3. After admin **Apply** or CLI init touching env: call `reload_settings()` from `config.settings` so cached settings refresh.

Shared Anthropic shaping belongs in **`core/anthropic`**, not in cross-importing provider `request.py` modules.
