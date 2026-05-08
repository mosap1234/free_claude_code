# OpenAI-Compatible Local Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a generic OpenAI-compatible provider path for local vLLM/SGLang-style `/v1/chat/completions` servers.

**Architecture:** Keep the existing FastAPI/API/provider architecture and add one minimal provider, `openai_compatible`, that reuses `OpenAIChatTransport` and the shared Anthropic-to-OpenAI conversion helpers. This is the first migration slice: it proves Claude Code can use a local OpenAI-compatible backend without copying messaging, CLI subprocess, voice, or native Anthropic provider machinery.

**Tech Stack:** Python 3.14, FastAPI existing API layer, Pydantic settings, existing `OpenAIChatTransport`, Ruff, Ty, Pytest.

---

### Task 1: Provider Catalog and Settings

**Files:**
- Modify: `config/provider_catalog.py`
- Modify: `config/settings.py`
- Modify: `.env.example`
- Test: `tests/config/test_config.py`
- Test: `tests/providers/test_registry.py`

- [x] **Step 1: Write failing config tests**

Add tests asserting that `openai_compatible/local-model` parses as a supported provider, `OPENAI_COMPATIBLE_BASE_URL` defaults to `http://localhost:8000/v1`, and the provider catalog descriptor uses OpenAI chat transport without a required credential.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/config/test_config.py tests/providers/test_registry.py -q`

Expected: failures mentioning unsupported provider or missing `openai_compatible` settings fields.

- [x] **Step 3: Add config/catalog implementation**

Add:

```python
OPENAI_COMPATIBLE_DEFAULT_BASE = "http://localhost:8000/v1"
```

Add settings fields:

```python
openai_compatible_api_key: str = Field(default="local", validation_alias="OPENAI_COMPATIBLE_API_KEY")
openai_compatible_base_url: str = Field(default="http://localhost:8000/v1", validation_alias="OPENAI_COMPATIBLE_BASE_URL")
openai_compatible_proxy: str = Field(default="", validation_alias="OPENAI_COMPATIBLE_PROXY")
```

Add a `ProviderDescriptor` for `openai_compatible` with `transport_type="openai_chat"`, static or optional local credential behavior, default base URL, base URL attr, proxy attr, and capabilities `("chat", "streaming", "tools", "thinking", "local")`.

- [x] **Step 4: Run focused tests and verify GREEN**

Run: `uv run pytest tests/config/test_config.py tests/providers/test_registry.py -q`

Expected: related config/registry tests pass.

### Task 2: Generic OpenAI-Compatible Provider

**Files:**
- Create: `providers/openai_compatible/__init__.py`
- Create: `providers/openai_compatible/client.py`
- Create: `providers/openai_compatible/request.py`
- Modify: `providers/registry.py`
- Test: `tests/providers/test_openai_compatible.py`
- Test: `tests/contracts/test_feature_manifest.py`

- [x] **Step 1: Write failing provider tests**

Add tests for provider initialization, request body conversion, model list behavior, and streaming delegation using the existing `OpenAIChatTransport` shape.

- [x] **Step 2: Run provider tests and verify RED**

Run: `uv run pytest tests/providers/test_openai_compatible.py tests/contracts/test_feature_manifest.py -q`

Expected: import or unknown provider failures.

- [x] **Step 3: Implement provider**

Create a provider class:

```python
class OpenAICompatibleProvider(OpenAIChatTransport):
    """Generic local OpenAI-compatible provider for vLLM/SGLang."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OPENAI_COMPATIBLE",
            base_url=config.base_url or OPENAI_COMPATIBLE_DEFAULT_BASE,
            api_key=config.api_key or "local",
        )

    def _build_request_body(self, request: Any, thinking_enabled: bool | None = None) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
```

Use `build_base_request_body()` with `ReasoningReplayMode.REASONING_CONTENT` when thinking is enabled and `ReasoningReplayMode.DISABLED` otherwise. Set `parallel_tool_calls` to `False` by default for Claude Code tool workflow stability.

- [x] **Step 4: Wire registry factory**

Add `_create_openai_compatible()` and register it in `PROVIDER_FACTORIES`.

- [x] **Step 5: Run provider tests and verify GREEN**

Run: `uv run pytest tests/providers/test_openai_compatible.py tests/contracts/test_feature_manifest.py -q`

Expected: provider tests pass.

### Task 3: API-Level Smoke Shape

**Files:**
- Modify: `tests/api/test_model_router.py`
- Modify: `tests/api/test_dependencies.py`
- Modify: `tests/api/test_model_listing.py`

- [x] **Step 1: Write failing API tests**

Add tests that a direct model id like `openai_compatible/qwen2.5-coder` routes to provider id `openai_compatible`, and that provider resolution returns `OpenAICompatibleProvider`.

- [x] **Step 2: Run focused API tests and verify RED or existing GREEN**

Run: `uv run pytest tests/api/test_model_router.py tests/api/test_dependencies.py tests/api/test_model_listing.py -q`

Expected: before implementation these fail; after Tasks 1-2 they should pass or require small API expectations.

- [x] **Step 3: Add missing API expectations**

If model list or dependency tests need explicit coverage, add `openai_compatible` to the expected provider sets and mock settings.

- [x] **Step 4: Run focused API tests and verify GREEN**

Run: `uv run pytest tests/api/test_model_router.py tests/api/test_dependencies.py tests/api/test_model_listing.py -q`

Expected: focused API tests pass.

### Task 4: Docs and Verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/claude-code-openai-proxy-migration.md`

- [x] **Step 1: Document local provider config**

Add examples:

```dotenv
OPENAI_COMPATIBLE_BASE_URL="http://127.0.0.1:8000/v1"
OPENAI_COMPATIBLE_API_KEY="local"
MODEL="openai_compatible/your-local-model"
```

Mention vLLM/SGLang as intended local OpenAI-compatible servers.

- [x] **Step 2: Run formatting and checks**

Run:

```bash
uv run ruff format
uv run ruff check
uv run ty check
uv run pytest
```

Expected: all checks pass.

- [x] **Step 3: Commit implementation**

Commit with:

```bash
git add config providers tests README.md .env.example docs
git commit -m "feat: add generic OpenAI-compatible provider"
```
