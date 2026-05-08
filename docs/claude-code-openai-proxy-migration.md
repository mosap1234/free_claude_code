# Claude Code to OpenAI-Compatible Proxy Migration Notes

This document summarizes how `free-claude-code` accepts Claude Code's
Anthropic-compatible API requests, routes them to providers, and converts
OpenAI-compatible streaming responses back into Anthropic SSE. It is written as
a migration guide for building a lighter proxy focused on local vLLM and SGLang
OpenAI-compatible servers.

## Target Use Case

The desired lightweight service should let Claude Code call a local proxy as if
it were an Anthropic API server:

```text
Claude Code -> local Anthropic-compatible proxy -> vLLM/SGLang OpenAI API
```

Claude Code speaks Anthropic Messages API. vLLM and SGLang commonly expose
OpenAI-compatible endpoints such as:

```text
GET  /v1/models
POST /v1/chat/completions
```

The proxy must therefore handle two conversions:

```text
Anthropic request body -> OpenAI chat/completions request body
OpenAI streaming chunks -> Anthropic SSE events
```

## Existing Project Call Chain

The main HTTP entry point is the FastAPI app factory:

- `api/app.py:create_app()`
- `api/routes.py:create_message()`
- `api/services.py:ClaudeProxyService.create_message()`
- `api/model_router.py:ModelRouter.resolve_messages_request()`
- `api/dependencies.py:resolve_provider()`
- `providers/registry.py:ProviderRegistry.get()`
- `providers/openai_compat.py:OpenAIChatTransport.stream_response()`
- `core/anthropic/sse.py:SSEBuilder`

For `/v1/messages`, the runtime flow is:

```text
1. Claude Code sends POST /v1/messages to the FastAPI server.
2. FastAPI validates the JSON body as MessagesRequest.
3. require_api_key() checks x-api-key, Authorization: Bearer, or anthropic-auth-token.
4. get_proxy_service() creates ClaudeProxyService with a provider_getter closure.
5. ClaudeProxyService.create_message() validates messages are non-empty.
6. ModelRouter resolves the incoming Claude model name to a provider/model pair.
7. The routed request is copied and request.model is changed to the provider model.
8. ProviderRegistry returns the provider instance for the resolved provider_id.
9. provider.preflight_stream() validates provider-specific request constraints.
10. ClaudeProxyService calculates input token count.
11. provider.stream_response() returns an async iterator of Anthropic SSE strings.
12. FastAPI wraps that iterator in StreamingResponse(text/event-stream).
13. Claude Code receives Anthropic-format SSE events.
```

The important architectural boundary is that the API layer does not know how a
specific provider talks to its upstream server. The provider owns request body
conversion, upstream I/O, stream parsing, error mapping, and Anthropic SSE
emission.

## OpenAI-Compatible Provider Path

The OpenAI-compatible conversion lives mainly in:

- `providers/openai_compat.py`
- `core/anthropic/sse.py`
- provider-specific request builders such as `providers/nvidia_nim/request.py`
- provider-specific client classes such as `providers/nvidia_nim/client.py` and
  `providers/kimi/client.py`

`OpenAIChatTransport` is the reusable base for providers that expose
`/chat/completions`. Its job is:

```text
1. Build an OpenAI-compatible request body from the routed Anthropic request.
2. Call AsyncOpenAI.chat.completions.create(..., stream=True).
3. Iterate over streamed OpenAI chunks.
4. Translate content, reasoning, tool calls, finish reasons, and usage into
   Anthropic SSE events.
```

The core streaming method is:

```text
providers/openai_compat.py:OpenAIChatTransport._stream_response_impl()
```

High-level pseudocode:

```python
sse = SSEBuilder(message_id, request.model, input_tokens)
body = self._build_request_body(request, thinking_enabled=thinking_enabled)

yield sse.message_start()

stream, body = await self._create_stream(body)
async for chunk in stream:
    choice = chunk.choices[0]
    delta = choice.delta

    if choice.finish_reason:
        finish_reason = choice.finish_reason

    if delta.reasoning_content:
        yield from sse.ensure_thinking_block()
        yield sse.emit_thinking_delta(delta.reasoning_content)

    if delta.content:
        yield from sse.ensure_text_block()
        yield sse.emit_text_delta(delta.content)

    if delta.tool_calls:
        yield from sse.close_content_blocks()
        yield from self._process_tool_call(tool_call, sse)

yield from sse.close_all_blocks()
yield sse.message_delta(map_stop_reason(finish_reason), output_tokens)
yield sse.message_stop()
```

The real implementation also handles `<think>` tags, heuristic tool-call parsing
from plain text, provider-specific reasoning hooks, task tool argument buffering,
retry-on-provider-field-rejection, rate limiting, error SSE emission, and token
usage fallback.

## Anthropic SSE Builder

`core/anthropic/sse.py:SSEBuilder` is the main reusable piece for response
formatting. It formats events as:

```text
event: <event_type>
data: <json>

```

The key methods are:

- `message_start()`
- `content_block_start()`
- `content_block_delta()`
- `content_block_stop()`
- `message_delta()`
- `message_stop()`
- `ensure_thinking_block()`
- `ensure_text_block()`
- `close_content_blocks()`
- `close_all_blocks()`
- `start_tool_block()`
- `emit_tool_delta()`

Claude Code expects a coherent Anthropic event order. A normal text response
looks like:

```text
message_start
content_block_start(index=0, type=text)
content_block_delta(index=0, type=text_delta)
content_block_delta(index=0, type=text_delta)
content_block_stop(index=0)
message_delta(stop_reason=end_turn)
message_stop
```

A tool-use response looks like:

```text
message_start
content_block_start(index=0, type=tool_use, id=..., name=...)
content_block_delta(index=0, type=input_json_delta, partial_json=...)
content_block_stop(index=0)
message_delta(stop_reason=tool_use)
message_stop
```

Thinking/reasoning responses use a `thinking` content block before a text block
when thinking is enabled:

```text
message_start
content_block_start(index=0, type=thinking)
content_block_delta(index=0, type=thinking_delta)
content_block_stop(index=0)
content_block_start(index=1, type=text)
content_block_delta(index=1, type=text_delta)
content_block_stop(index=1)
message_delta(stop_reason=end_turn)
message_stop
```

The stop reason conversion is:

```python
{
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}
```

## Request Conversion Responsibilities

For a lightweight vLLM/SGLang proxy, request conversion should be much smaller
than the current project. The minimum conversion layer needs to map:

```text
Anthropic model     -> OpenAI model
Anthropic system    -> OpenAI system message
Anthropic messages  -> OpenAI messages
Anthropic tools     -> OpenAI tools
Anthropic tool_choice -> OpenAI tool_choice, if supported
max_tokens          -> max_tokens
temperature/top_p   -> temperature/top_p
stream              -> true
```

The existing project contains more conversion logic because it supports several
providers and Claude Code edge cases. For a local-only proxy, start with:

```python
{
    "model": resolved_model,
    "messages": converted_messages,
    "tools": converted_tools_or_omitted,
    "tool_choice": converted_tool_choice_or_omitted,
    "temperature": request.temperature,
    "top_p": request.top_p,
    "max_tokens": request.max_tokens or default_max_tokens,
    "stream": True,
}
```

Claude content blocks need flattening. Typical cases:

- Anthropic text block -> OpenAI message content text
- Anthropic tool_result block -> OpenAI tool message
- Anthropic tool_use block in assistant history -> OpenAI assistant tool_calls
- Anthropic thinking block -> usually omit for local OpenAI servers, or preserve
  as provider-specific `reasoning_content` only if the target server supports it

The hardest migration area is not plain chat text. It is correct replay of tool
call history after Claude Code receives a tool request and sends the next turn
with `tool_result` blocks.

## Response Conversion Responsibilities

For streamed OpenAI chunks, preserve this mapping:

| OpenAI stream field | Anthropic SSE output |
| --- | --- |
| `delta.content` | text `content_block_delta` |
| `delta.reasoning_content` | thinking `content_block_delta`, if enabled |
| `<think>...</think>` in content | thinking block via parser, optional |
| `delta.tool_calls[].function.name` | `tool_use` block name |
| `delta.tool_calls[].id` | `tool_use` block id |
| `delta.tool_calls[].function.arguments` | `input_json_delta` |
| `choice.finish_reason="tool_calls"` | `message_delta.stop_reason="tool_use"` |
| `choice.finish_reason="stop"` | `message_delta.stop_reason="end_turn"` |
| `choice.finish_reason="length"` | `message_delta.stop_reason="max_tokens"` |
| `usage.prompt_tokens` | optional log comparison with local input estimate |
| `usage.completion_tokens` | `message_delta.usage.output_tokens` |

The implementation must maintain content block state. Before starting a tool
block, close any open text/thinking block. Before starting text after thinking,
close the thinking block. At the end, close all open blocks before emitting
`message_delta` and `message_stop`.

## Lightweight Architecture for vLLM/SGLang

Recommended minimal modules:

```text
app.py
  FastAPI app, routes, auth, settings injection

models.py
  Pydantic models for the subset of Anthropic Messages API needed by Claude Code

settings.py
  OPENAI_BASE_URL, OPENAI_API_KEY, MODEL, auth token, timeouts

router.py
  Resolve Claude model names or direct model names to the target OpenAI model

openai_request.py
  Anthropic request -> OpenAI chat/completions body

sse.py
  Anthropic SSEBuilder and stop reason mapping

openai_stream.py
  OpenAI stream -> Anthropic SSE async iterator

errors.py
  Upstream errors -> Anthropic error shape/SSE fallback
```

Avoid migrating these unless needed:

- Multi-provider registry
- Discord/Telegram messaging
- Claude CLI subprocess management
- Provider model discovery cache
- NVIDIA-specific retry downgrades
- Native Anthropic Messages transport
- Live smoke harness
- Provider-specific proxy settings
- Voice transcription

Keep or adapt these:

- `SSEBuilder`
- stop reason mapping
- OpenAI stream loop shape
- tool-call streaming state
- request conversion for messages/tools/tool results
- FastAPI `StreamingResponse` wrapper
- simple auth compatible with Claude Code headers

## Suggested Minimal Runtime Flow

```text
POST /v1/messages
  -> validate Anthropic request
  -> auth check
  -> resolve target model
  -> convert request body to OpenAI chat/completions
  -> call vLLM/SGLang /v1/chat/completions with stream=true
  -> stream OpenAI chunks
  -> emit Anthropic SSE using SSEBuilder
```

`/v1/messages/count_tokens` can initially use an approximate local estimator.
Claude Code generally needs the endpoint to exist and return:

```json
{"input_tokens": 123}
```

`/v1/models` can initially return configured model aliases instead of querying
the upstream server. Later, it can proxy `GET /v1/models` from vLLM/SGLang.

## vLLM and SGLang Notes

Both vLLM and SGLang are best treated as OpenAI-compatible upstreams:

```text
OPENAI_BASE_URL=http://127.0.0.1:8000/v1
OPENAI_API_KEY=local-or-empty
MODEL=your-local-model-name
```

Potential compatibility differences to test:

- Whether streamed chunks include `usage`
- Whether tool calls stream in separate name/argument fragments
- Whether tool call ids are present in the first tool delta
- Whether reasoning is emitted as `reasoning_content`, plain `<think>` text, or
  ordinary content
- Whether the server supports OpenAI `tools` and `tool_choice`
- Whether parallel tool calls need to be disabled
- Whether the model's chat template can produce valid JSON tool arguments

For a first version, make thinking optional and default it off. Tool calling is
more important for Claude Code workflows than preserving reasoning text.

The current migration branch implements the first reusable slice as a generic
`openai_compatible` provider inside this project. It is configured with:

```dotenv
OPENAI_COMPATIBLE_BASE_URL="http://127.0.0.1:8000/v1"
OPENAI_COMPATIBLE_API_KEY="local"
MODEL="openai_compatible/your-local-model"
```

This keeps the existing FastAPI/API/provider shell while proving the local
OpenAI `/chat/completions` conversion path against vLLM/SGLang-style servers.
The later extraction into a new lightweight project can copy the same provider
request/stream conversion pieces without the multi-provider registry, messaging,
voice, or Claude CLI subprocess layers.

## Migration Strategy

Recommended sequence:

1. Copy or reimplement a small `SSEBuilder`.
2. Implement a text-only `/v1/messages` path.
3. Add OpenAI stream parsing for `delta.content`, `finish_reason`, and usage.
4. Add `/v1/messages/count_tokens` with approximate counting.
5. Add `/v1/models` returning configured model ids.
6. Add request conversion for Anthropic `tools`.
7. Add response conversion for OpenAI `tool_calls`.
8. Add history replay conversion for prior `tool_use` and `tool_result` blocks.
9. Add optional reasoning support for `reasoning_content` and `<think>` tags.
10. Add upstream error mapping and mid-stream SSE error behavior.

Do not start by copying the whole provider registry. The smallest useful proxy
only needs one configurable OpenAI-compatible upstream.

## Test Cases to Preserve

Minimum deterministic tests:

- Text-only request returns valid Anthropic SSE event order.
- Multiple OpenAI `delta.content` chunks become multiple `text_delta` events.
- OpenAI `finish_reason="stop"` becomes Anthropic `end_turn`.
- OpenAI `finish_reason="length"` becomes Anthropic `max_tokens`.
- OpenAI `finish_reason="tool_calls"` becomes Anthropic `tool_use`.
- Streamed tool call name and arguments become one Anthropic `tool_use` block.
- Split tool-call arguments are emitted as `input_json_delta` fragments.
- Text block closes before a tool block starts.
- Thinking block closes before a text block starts.
- Upstream HTTP errors produce Anthropic-compatible errors.
- `/v1/messages/count_tokens` returns a valid integer shape.
- `/v1/models` returns a Claude Code-compatible models list shape.

Manual smoke tests against local servers:

```text
vLLM text-only prompt
vLLM tool-use prompt
SGLang text-only prompt
SGLang tool-use prompt
Claude Code interactive session using ANTHROPIC_BASE_URL
Claude Code tool workflow that reads/writes a small file
```

## Recommended Borrow List

Borrow conceptually or directly:

- `core/anthropic/sse.py:SSEBuilder`
- `core/anthropic/sse.py:map_stop_reason`
- `providers/openai_compat.py:_stream_response_impl()` structure
- `providers/openai_compat.py:_process_tool_call()` state handling
- `api/services.py:anthropic_sse_streaming_response()`
- `api/dependencies.py:require_api_key()` header compatibility

Reimplement lightly:

- settings
- model routing
- request conversion
- error mapping
- token counting
- model listing

Avoid initially:

- all messaging modules
- all native Anthropic provider modules
- all provider registry/catalog machinery
- product smoke framework
- voice transcription
- provider-specific hacks unless vLLM/SGLang need one

## Key Design Principle

For a local vLLM/SGLang proxy, keep the service shaped around one boundary:

```text
Claude Code Anthropic compatibility at the edge,
OpenAI-compatible chat/completions compatibility upstream.
```

Everything else should be optional. The project becomes easier to reason about
when the conversion layer is explicit, stateful only for streaming content
blocks, and tested with small synthetic OpenAI chunks before testing against
real local model servers.
