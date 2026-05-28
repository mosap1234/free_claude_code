# Changelog — Luiz-crypto-cmd fork

## Fix: Claude Code 2.1.152 + DeepSeek thinking — multi-turn 400 error (2026-05-27)

### Problem

After Claude Code auto-updated to **2.1.152** on May 27, 2026, all multi-turn conversations with
DeepSeek (deepseek-v4-pro / deepseek-reasoner) started failing with:

```
● Invalid request sent to provider.
  Request ID: req_xxxxxxxx
```

The underlying HTTP error from DeepSeek:
```json
{"error": {"message": "The `content[].thinking` in the thinking mode must be passed back to the API.", "type": "invalid_request_error"}}
```

### Root cause

Claude Code **2.1.152** added a cryptographic signature requirement for thinking blocks:
it only stores thinking blocks in conversation history if they carry a valid `signature` field
signed by Anthropic's infrastructure.

DeepSeek's Anthropic-compatible API does **not** emit `signature_delta` events (it's not
Anthropic's real infrastructure). So:

1. Turn 1: DeepSeek generates thinking → proxy forwards it → Claude Code **discards it** (no signature)
2. Turn 2: Claude Code sends history without thinking blocks → DeepSeek requires them → **HTTP 400**

deepseek-v4-pro is an always-on reasoning model: it requires prior thinking blocks in **all**
assistant turns with tool_use, regardless of whether thinking is explicitly requested in the
current turn.

### Fix (2 files)

**`providers/deepseek/request.py`** — `_inject_placeholder_thinking_blocks()`

When the proxy detects assistant messages in history that have `tool_use` blocks but no
`thinking` block (because Claude Code dropped them), it injects a minimal placeholder:

```python
{"type": "thinking", "thinking": "(prior reasoning not available)"}
```

This satisfies DeepSeek's history validation. The model still generates full real thinking
on every new response.

**`core/anthropic/native_sse_block_policy.py`** — synthetic `signature_delta`

Injects a `signature_delta` SSE event before each `content_block_stop` for thinking blocks.
This causes Claude Code to store thinking blocks in history when the signature validation
is not strictly enforced (forward-compatibility fix).

**`config/logging_config.py`** — Windows restart fix

Replaced manual `Path.write_text("")` truncation with `mode="w"` on the loguru file sink,
fixing a `PermissionError` on Windows when restarting the gateway while the previous
process still held the log file handle.

### Affected versions

- Claude Code ≥ 2.1.152
- DeepSeek provider (deepseek-v4-pro, deepseek-reasoner, any always-on reasoning model)
- All other providers unaffected

### Upstream

Based on [free-claude-code](https://github.com/Alishahryar1/free-claude-code) by Ali Khokhar (MIT).
