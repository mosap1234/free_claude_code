# Bolt's Journal - Performance Optimizations

## 2024-05-24 - Avoid O(N) Set Reconstructions in High-Frequency Cache Purges
**Learning:** In python, rebuilding an entire cache set using a comprehension on a truncated list (e.g. `set(x for x in list[-cap:])`) is O(N) and creates unnecessary garbage. When a cache reaches its cap during a single item append, it is significantly faster to remove only the single oldest item using `set.discard()` which is O(1).
**Action:** When capping a rolling window, calculate the exact dropped items and `discard` them individually from the tracking set rather than rebuilding the tracking set from scratch.

## 2026-05-12 - Systemic Performance Overhaul
**Learning:** Systemic overhead from repeated filesystem lookups (Path.home, Path.resolve) and environment variable parsing can add up to 20-30ms per request in a local FastAPI app. Pre-calculating static manifests and using lru_cache for pure string-to-string mappings (token counting, model ID decoding) reduces this overhead by ~90%.
**Action:** Always prefer module-level pre-calculation for static UI manifests. Use lru_cache for token counting and environment file lookups where the content is stable during the process lifetime.

## 2026-05-12 - Nvidia NIM Connectivity Optimization & Timeout Resilience
**Learning:** Large-scale token processing (e.g., codebase audits) can trigger 300s+ read stalls on upstream NIM endpoints. Standard 120s timeouts are insufficient. Furthermore, transient connection stalls during stream initiation require proactive retries to avoid hard failures in the client.
**Action:** 
1. Increased default HTTP_READ_TIMEOUT to 600s across all providers.
2. Modified GlobalRateLimiter to treat httpx.TimeoutException and openai.APITimeoutError as retryable events (Status 408).
3. Increased SDK max_retries to 2 in OpenAIChatTransport to handle transient connection resets.

## 2024-05-25 - Avoid redundant property lookups in high-frequency loops
**Learning:** Repeated calls to helpers like `hasattr` and `isinstance` inside tight loops (like token counting over thousands of blocks) cause significant overhead. `hasattr` internally executes `getattr` which doubles property access time.
**Action:** Use `getattr(obj, attr, default)` directly instead of `hasattr`, and when processing lists of mixed types (dicts vs objects), cache the `is_dict = isinstance(obj, dict)` check once per element before accessing its attributes.
