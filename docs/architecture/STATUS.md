# Architecture program status

Snapshot of items from [IMPROVEMENT_PLAN Definition of done](IMPROVEMENT_PLAN.md) and the consolidated roadmap. Update this file when milestones land.

| Criterion | Status | Notes |
|-----------|--------|-------|
| `config/settings.py` composition hub (~320 lines target) | Partial | Mixins live in `config/settings_*.py`; validators in [`config/settings_validators.py`](../../config/settings_validators.py); dotenv/migration guards in [`config/settings_env.py`](../../config/settings_env.py); [`config/settings.py`](../../config/settings.py) is glue + bundles (~315 lines). |
| `core/anthropic/conversion/_conversion.py` removed | Done | Submodules live under [`core/anthropic/conversion/](../../core/anthropic/conversion/). |
| At least four OpenAI-chat providers use catalog factory | Done | See [`providers/registry.py`](../../providers/registry.py) `_instantiate_catalog_openai_chat` / `PARTIAL`/catalog rows. |
| `api/runtime.py` under ~220 lines; bootstrap in `messaging/bootstrap.py` | Partial | Bootstrap options + tree restore remain in [`messaging/bootstrap.py`](../../messaging/bootstrap.py); CLI + handler wiring in [`api/messaging_startup.py`](../../api/messaging_startup.py); [`api/runtime.py`](../../api/runtime.py) ~256 lines. |
| `reload_settings()` at all reload sites | Done | Admin, CLI entrypoints, smoke config (see codebase grep). Tests in [`tests/config/test_config.py`](../../tests/config/test_config.py). |
| `docs/architecture/` layers, provider resolution, messaging | Done | [`layers.md`](layers.md), [`messaging.md`](messaging.md), [`api-package.md`](api-package.md), [`admin.md`](admin.md). |
| `tests/contracts/test_provider_wiring.py` alignment guards | Done | Catalog / admin credential / factories. |
| Import-boundary contract tests green | Maintain | [`tests/contracts/test_import_boundaries.py`](../../tests/contracts/test_import_boundaries.py). |

## Consolidated roadmap (post–IMPROVEMENT_PLAN)

| Track | Purpose |
|-------|---------|
| Transport vs ingress errors | Done | [`api/ingress_errors.py`](../../api/ingress_errors.py) + [`api/ingress_handlers.py`](../../api/ingress_handlers.py): domain ingress errors → `{"detail": ...}`. Uncaught [`ProviderError`](../../providers/exceptions.py) still uses Anthropic JSON in [`api/app.py`](../../api/app.py). |
| Admin env persistence split | [`api/admin_env_read.py`](../../api/admin_env_read.py), [`api/admin_env_write.py`](../../api/admin_env_write.py), [`api/admin_env_shared.py`](../../api/admin_env_shared.py); stable façade [`api/admin_persistence.py`](../../api/admin_persistence.py). |
| Resolver semantics tests | [`tests/contracts/test_provider_resolution_semantics.py`](../../tests/contracts/test_provider_resolution_semantics.py). |
| Native messages + OpenAI-compat helpers | [`providers/native_messages_support.py`](../../providers/native_messages_support.py); tool-arg streaming split [`providers/openai_compat_tool_args.py`](../../providers/openai_compat_tool_args.py) + [`providers/openai_compat.py`](../../providers/openai_compat.py). |

**Deferred milestones:** [`deferred_milestones.md`](deferred_milestones.md).
