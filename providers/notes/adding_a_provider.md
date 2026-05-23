# Adding a provider

Follow this checklist whenever you introduce or substantially change an upstream backend. Keeps **`PROVIDER_CATALOG`**, **`PROVIDER_FACTORIES`**, Admin UI fields, `.env.example`, and contract tests aligned.

## 1. Catalog

Edit **`config/provider_catalog.py`**:

- Add one `ProviderDescriptor` entry with **`provider_id`**, **`transport_type`** (`openai_chat` vs `anthropic_messages`), **`registry_factory`** (name of `_create_*` in `providers/registry.py`).
- Configure **`credential_env`** / **`credential_attr`** / **`credential_url`** (or **`static_credential`** for locals).
- For native Anthropic HTTP adapters, set **`native_stream_chunk_mode`** and **`native_messages_header_profile`** when not defaults.

Native transport deltas inventory: **`native_anthropic_http_providers.md`**.

## 2. Registry

Edit **`providers/registry.py`**:

- Implement **`_create_<id>(config, settings)`** referenced by **`registry_factory`**, or use the catalog-driven OpenAI path where applicable.
- Ensure **`PROVIDER_FACTORIES`** auto-build stays in sync with the catalog (`tests/contracts/test_architecture_contracts.py`).

## 3. Adapter implementation

- **OpenAI chat:** Extend **`OpenAIChatTransport`** (or **`CatalogOpenAIChatProvider`** pattern) plus per-provider **`request.py`** **`build_request_body`**.
- **Native Anthropic messages:** Extend **`AnthropicMessagesTransport`**; shared shaping stays in **`core/anthropic`**.

Do **not** import another provider’s **`request`** module — extract to **`core/anthropic`**.

## 4. Admin UI

Edit **`api/admin/fields_providers.py`** (and related **`fields_*`**):

- Each **`credential_env`** should have a **`ConfigFieldSpec`** whose **`key`** matches that env var and **`settings_attr`** matches the **`Settings`** field name consumed by **`credential_attr`** in the descriptor.

## 5. Env template

Add keys (or commented placeholders) to **`.env.example`** for every **`credential_env`**.

## 6. Automated wiring checks

Extend or satisfy **`tests/contracts/test_provider_wiring.py`**:

- Catalog keys ↔ factories
- Credential env vars ↔ admin field keys ↔ `Settings.model_fields`
- Credential env vars ↔ `.env.example`

## 7. Behavior tests

Add **`tests/providers/test_<provider_id>.py`** (or extend existing suites). Prefer golden / focused tests around request bodies and SSE where behavior is brittle.

## 8. Smoke capability map

Update **`smoke/capabilities.py`** **`CapabilityContract`** rows when the change affects a public integration surface tracked there.
