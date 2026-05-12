# Bolt's Journal - Performance Optimizations

## 2024-05-24 - Avoid O(N) Set Reconstructions in High-Frequency Cache Purges
**Learning:** In python, rebuilding an entire cache set using a comprehension on a truncated list (e.g. `set(x for x in list[-cap:])`) is O(N) and creates unnecessary garbage. When a cache reaches its cap during a single item append, it is significantly faster to remove only the single oldest item using `set.discard()` which is O(1).
**Action:** When capping a rolling window, calculate the exact dropped items and `discard` them individually from the tracking set rather than rebuilding the tracking set from scratch.

## 2026-05-12 - Systemic Performance Overhaul
**Learning:** Systemic overhead from repeated filesystem lookups (Path.home, Path.resolve) and environment variable parsing can add up to 20-30ms per request in a local FastAPI app. Pre-calculating static manifests and using lru_cache for pure string-to-string mappings (token counting, model ID decoding) reduces this overhead by ~90%.
**Action:** Always prefer module-level pre-calculation for static UI manifests. Use lru_cache for token counting and environment file lookups where the content is stable during the process lifetime.
