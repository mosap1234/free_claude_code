## 2024-05-24 - Avoid O(N) Set Reconstructions in High-Frequency Cache Purges
**Learning:** In python, rebuilding an entire cache set using a comprehension on a truncated list (e.g. `set(x for x in list[-cap:])`) is O(N) and creates unnecessary garbage. When a cache reaches its cap during a single item append, it is significantly faster to remove only the single oldest item using `set.discard()` which is O(1).
**Action:** When capping a rolling window, calculate the exact dropped items and `discard` them individually from the tracking set rather than rebuilding the tracking set from scratch.
