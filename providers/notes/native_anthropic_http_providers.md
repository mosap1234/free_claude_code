# Native Anthropic HTTP transport (`AnthropicMessagesTransport`) deltas

This note inventories first-party-style providers that inherit
`AnthropicMessagesTransport` (`providers/anthropic_messages.py`) today. The goal
is to **dedupe deltas** (headers, `stream_chunk_mode`, request body builders, and
sanitize hooks) using small strategy modules or catalog flags alongside the shared
**`httpx` + SSE** pipeline (`core/anthropic`).

## Subclasses (manual `httpx` streaming)

| Adapter | Module | Typical stream / body notes |
| --- | --- | --- |
| `LmStudioProvider` | `providers/lmstudio/client.py` | Local LM Studio native messages |
| `LlamaCppProvider` | `providers/llamacpp/client.py` | llama.cpp server compatibility |
| `OllamaProvider` | `providers/ollama/client.py` | Ollama native `/v1/messages` quirks |
| `OpenRouterProvider` | `providers/open_router/client.py` | `stream_chunk_mode="event"` tier |
| `DeepSeekProvider` | `providers/deepseek/client.py` | Request sanitization (`deepseek/request`) |
| `WaferProvider` | `providers/wafer/client.py` | Hosted Anthropic-compat endpoint |

Keep OpenAI-chat gateways (`AsyncOpenAI` + SSE conversion) **separate**: they do
not use this inheritance chain.

## Suggested convergence (when touching these files)

1. Prefer **explicit per-`provider_id` strategy structs** next to catalog entries over
   one-off subclass branches when differences are headers or stream flags only.
2. Never cross-import adapter `*_request.py` modules from each other—shared shaping
   belongs in **`core/anthropic`** builders (`AGENTS.md`).
