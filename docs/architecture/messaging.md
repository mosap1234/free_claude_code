# Messaging bounded contexts

Optional bot integration (`messaging`) is layered so it stays independent of HTTP routes and upstream providers.

## Contexts

| Context | Responsibility | Typical modules |
|---------|----------------|-----------------|
| Ingress | Translate platform updates into inbound user turns | `platforms/*/handlers.py`, `incoming_turn.py`, `platforms/factory.py` |
| Orchestration | Queue ordering, Claude CLI drives, handler coordination | `handler.py`, `trees/*`, `claude_node_processor.py`, `command_dispatcher.py` |
| Presentation | Markdown, truncation, status UX | `rendering/*`, `handler_queue_ux.py`, `transcript*.py`, `ui_updates.py` |
| Session persistence | Stored trees and mappings | `session.py`, tree sync from handler |

Composition root: **`api.runtime.AppRuntime`** starts messaging in two steps:

1. **`messaging/bootstrap.py`** — maps [`Settings`](../../config/settings.py) to [`MessagingPlatformOptions`](../../messaging/platforms/factory.py) (tokens, transcription backend, limits) and creates the platform; restores conversation trees from persisted session data when wiring the handler.
2. **`api/messaging_startup.py`** — builds [`CLISessionManager`](../../cli/manager.py), [`SessionStore`](../../messaging/session.py), and [`ClaudeMessageHandler`](../../messaging/handler.py), then attaches the handler and starts the platform (`messaging` must not import `cli`).

Messaging must never import `providers.*` dynamically; see `tests/contracts/test_messaging_dynamic_providers.py`.

## Inbound sequence (high level)

```mermaid
sequenceDiagram
  participant Platform as PlatformWebhook
  participant Ingress as messaging_ingress
  participant Handler as ClaudeMessageHandler
  participant CLI as CLISessionManager
  participant Upstream as Provider_or_ClaudeCLI

  Platform->>Ingress: platform_update
  Ingress->>Handler: inbound_turn
  Handler->>CLI: enqueue_or_drive_session
  CLI->>Upstream: model_request
  Upstream-->>CLI: stream_or_response
  CLI-->>Handler: CLI_events
  Handler->>Platform: outbound_message_or_embed
```

## Outbound sequence (high level)

```mermaid
sequenceDiagram
  participant Handler as ClaudeMessageHandler
  participant Trees as trees_queue
  participant Render as rendering
  participant Platform as MessagingPlatform

  Handler->>Trees: dequeue_or_merge
  Handler->>Render: format_markdown_and_limits
  Render-->>Handler: platform_payload
  Handler->>Platform: send_or_edit_message
```

## Public surface

Stable symbols for tests and external wiring are re-exported from [`messaging/__init__.py`](../../messaging/__init__.py). Prefer importing from that package rather than deep leaves when adding new integration code, so tests can patch the façade module when needed.

## Outbound typing

[`PlatformOutbound`](../../messaging/platforms/outbound.py) narrows the queued send/edit surface consumed by [`messaging/handler.py`](../../messaging/handler.py) and command helpers. Implementations remain concrete [`MessagingPlatform`](../../messaging/platforms/base.py) subclasses.
