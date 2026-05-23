# Architecture program status

Snapshot of items from [IMPROVEMENT_PLAN Definition of done](IMPROVEMENT_PLAN.md) and the consolidated roadmap. Update this file when milestones land.

| Criterion | Status | Notes |
|-----------|--------|-------|
| `config/settings.py` under ~200 lines (composition only) | Partial | Mixins live in `config/settings_*.py`; `settings.py` remains ~463 lines due to validators, `Settings` composite class, bundles, `get_settings`/`reload_settings`. Further slimming optional. |
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
| Transport vs resolver errors | [`api/resolver_exceptions.py`](../../api/resolver_exceptions.py): subclasses of `HTTPException` centralizing resolver and gateway-auth responses. |
| Admin env persistence split | [`api/admin_env_read.py`](../../api/admin_env_read.py), [`api/admin_env_write.py`](../../api/admin_env_write.py), [`api/admin_env_shared.py`](../../api/admin_env_shared.py); stable façade [`api/admin_persistence.py`](../../api/admin_persistence.py). |
| Resolver semantics tests | [`tests/contracts/test_provider_resolution_semantics.py`](../../tests/contracts/test_provider_resolution_semantics.py). |
| Native messages transport helpers | [`providers/native_messages_support.py`](../../providers/native_messages_support.py) extracted from [`providers/anthropic_messages.py`](../../providers/anthropic_messages.py); further `openai_compat` decomposition optional. |

**Deferred milestones:** [`deferred_milestones.md`](deferred_milestones.md).
