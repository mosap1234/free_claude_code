# Admin UI trust boundary

The local **Admin** surface (`/admin`, `/admin/api/*`) manipulates **managed environment files**, **in-process settings cache**, and **provider registry** instances. Treat it as a **high-privilege control plane** even though it is not exposed to the public internet by default.

## Network exposure

- Admin HTML and JSON routes are **loopback-only** by design (see [`tests/api/test_admin.py`](../../tests/api/test_admin.py) `test_admin_page_is_loopback_only`). Remote clients receive **403**.
- Do not weaken this check for convenience; if you need remote admin, put an authenticated reverse proxy in front instead of binding the check to `0.0.0.0` without TLS and auth.

## Data handled

- **Secrets:** Field specs mark `secret` values; UI masks them with `MASKED_SECRET`. Writes go to the **managed env file** under the user data directory ([`api/admin_env_write.write_managed_env`](../../api/admin_env_write.py)).
- **Process environment:** Keys present in the process environment are treated as **locked** sources and are not overwritten by Apply (see [`api/admin_env_shared.is_locked_source`](../../api/admin_env_shared.py)).
- **Runtime:** After Apply, [`reload_settings()`](../../config/settings.py) runs and the app may rebuild rate limiters and **rotate** `app.state.provider_registry` (see [`api/admin_routes.py`](../../api/admin_routes.py)).

## Module layout

| Module | Role |
|--------|------|
| [`api/admin_env_read.py`](../../api/admin_env_read.py) | Discover dotenv files, merge precedence, `load_config_response`, provider status snapshot. |
| [`api/admin_env_write.py`](../../api/admin_env_write.py) | Validate against `Settings`, render env file, atomic write. |
| [`api/admin_env_shared.py`](../../api/admin_env_shared.py) | Normalization and shared validation helpers. |
| [`api/admin_persistence.py`](../../api/admin_persistence.py) | Stable import path re-exporting read/write entry points (backwards compatible). |

## Related

- Orientation: [api-package.md](api-package.md)
- Status checklist: [STATUS.md](STATUS.md)
