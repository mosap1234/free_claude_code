# Messaging bounded contexts

Optional bot integration (`messaging`) is layered so it stays independent of HTTP routes and upstream providers.

## Contexts

| Context | Responsibility | Typical modules |
|---------|----------------|-----------------|
| Ingress | Translate platform updates into inbound user turns | `platforms/*/handlers.py`, `incoming_turn.py`, `platforms/factory.py` |
| Orchestration | Queue ordering, Claude CLI drives, handler coordination | `handler.py`, `trees/*`, `claude_node_processor.py`, `command_dispatcher.py` |
| Presentation | Markdown, truncation, status UX | `rendering/*`, `handler_queue_ux.py`, `transcript*.py`, `ui_updates.py` |
| Session persistence | Stored trees and mappings | `session.py`, tree sync from handler |

Composition root: **`api.runtime.AppRuntime`** starts messaging via **`messaging/bootstrap.py`** factory options (tokens, transcription backend, limits). Messaging must never import `providers.*` dynamically; see `tests/contracts/test_messaging_dynamic_providers.py`.
