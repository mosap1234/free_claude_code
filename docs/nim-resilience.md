# NIM Resilience — design

A multi-phase plan to make `nvidia_nim` provider sessions survive transient
upstream failures without losing user work.

## Why this matters

NIM free tier is the only no-cost path to 80B–675B class open-weight models for
agentic Claude Code work. But it has several failure modes that today break
sessions catastrophically:

1. **5-minute hard stream cap** — single requests that take >5min get a 504
   Gateway Timeout. We've observed this on Qwen3-Coder-480B during long
   thinking turns over 50+ message conversations.
2. **Function cold-start 404s** — NIM unloads model functions after idle and
   returns 404 on the first call until the function reloads. Common on the
   biggest models (Nemotron-Ultra-253B, Nemotron-4-340B). Confirmed via
   opencode logs.
3. **502/503 transient errors** — NIM gateway hiccups. Routine, retryable.
4. **`RemoteProtocolError`** — connection dropped mid-stream by NIM's edge.
5. **`ReadTimeout`** — connection sits open with no bytes; httpx eventually
   gives up after default ~5min, but the proxy "succeeds" silently for hours
   in the meantime. Observed: 8.5h hang.
6. **429 rate limits** — already retried (3× exponential backoff).

The architecture below makes every interruption a checkpoint instead of a
failure. Built in four phases so each is reviewable and shippable on its own.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code (outer loop)                                        │
└────┬────────────────────────────────────────────────────────────┘
     │  /v1/messages POST per turn
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  fcc proxy (per-request lifecycle)                               │
│                                                                   │
│  PRE-REQUEST                                                      │
│   ├─ fingerprint conversation (Phase 3)                          │
│   ├─ load session memory from local store (Phase 3)              │
│   ├─ inject as system frame (Phase 3)                            │
│   └─ governor (existing — tier caps, tool cull, preambles)       │
│                                                                   │
│  COMPACTION (Phase 2)                                             │
│   ├─ working memory   — last ~15 turns, full fidelity            │
│   ├─ compressed mem   — turns 16-50, paragraph summaries         │
│   ├─ long-term mem    — turns 51+, sentence facts                │
│   └─ time-safe budget per provider: NIM=80k, OR=160k             │
│                                                                   │
│  STREAM (Phase 1, this branch)                                    │
│   ├─ retry classifier   — 502/503/504/timeouts/404-cold-start    │
│   ├─ stream watchdog    — 90s silence → clean abort              │
│   ├─ time-pressure      — soft wrap-up at 240s, hard at 280s     │
│   └─ pre/mid-stream split — retry only when zero tokens emitted  │
│                                                                   │
│  POST-RESPONSE                                                    │
│   ├─ extract delta (Phase 3)                                     │
│   ├─ checkpoint to store (Phase 3)                               │
│   └─ on failure: synthesize "continue" response (Phase 4)        │
└─────────────────────────────────────────────────────────────────┘
```

## Phase 1 — Transport resilience (this PR)

In scope:

* Extend `execute_with_retry` to retry transient errors:
  - HTTP 502, 503, 504 (gateway errors)
  - HTTP 408 (request timeout)
  - HTTP 520, 522, 524 (Cloudflare upstream)
  - HTTP 404 with body `"Function ... Not found for account"` (NIM cold-start)
  - `httpx.ConnectError`, `httpx.ConnectTimeout`
  - `httpx.ReadTimeout` (only pre-stream)
  - `httpx.RemoteProtocolError`
  - `openai.APIConnectionError`, `openai.APITimeoutError`
* Same backoff strategy as 429: exponential with jitter, configurable retry count.
* New `core/stream_watchdog.py` — async wrapper around an SSE iterator that
  raises if no token arrives within `silence_timeout_s`.
* Track `first_token_emitted` flag in `_stream_response_impl`. If an error
  fires before any token is emitted, re-raise into the retry layer for
  transparent recovery. If it fires after, emit a clean SSE error event and
  log clearly.
* NIM-aware HTTP timeout defaults:
  - connect=10s
  - write=60s
  - read=320s (matches NIM's 5-min cap + buffer)
  - pool=10s
* Structured retry telemetry — `NIM_RETRY:` log lines with attempt, cause, backoff.
* Configuration via env:
  - `NIM_RETRY_MAX_ATTEMPTS=4`
  - `NIM_RETRY_BASE_DELAY_S=2.0`
  - `NIM_RETRY_MAX_DELAY_S=30.0`
  - `NIM_RETRY_JITTER_S=1.5`
  - `NIM_STREAM_SILENCE_TIMEOUT_S=90`
  - `NIM_RETRY_ON_5XX=502,503,504,520,522,524`

Out of scope (later phases):

* Time-safe context compaction (Phase 2)
* Hierarchical memory + session checkpoints (Phase 3)
* Resume tokens + dynamic summarization (Phase 4)

## Phase 2 — Time-safe compaction (next PR)

* NIM context budget retune (262k → ~80k effective)
* Summarize-then-trim using nemotron-nano-30b
* Hierarchical memory tiers (working / compressed / long-term)
* Time-pressure preamble injection at soft timeout

## Phase 3 — Session memory (PR after that)

* SQLite-backed session store at `~/.cache/free-claude-code/sessions.db`
* Conversation fingerprinting (hash of first user msg + system prefix)
* Per-turn delta extraction (tools called, files touched, decisions)
* Optional mempalace mirror via env flag

## Phase 4 — Resume tokens (final PR)

* On forced abort, synthesize a structured "continuing" response
* Resume token format: JSON in a system frame, includes goal / done / next
* Inject into the next turn's system message so the model picks up cleanly
* "Always continue" — every endpoint is a checkpoint, never a dead end

## Out of scope across all phases

* **Cross-provider failover.** The whole point of fcc with NIM is staying on
  NIM. If you need a fallback provider, switch model alias manually via
  `claude-fcc -m or-coder`.
* **Multi-region NIM routing.** NIM's regional endpoints aren't documented
  enough to round-robin reliably.
* **Model autoswitch by latency.** A separate optimization — could route
  routine queries to nano-30b and tool-heavy queries to coder-480b — but
  that's a feature, not a resilience fix.
