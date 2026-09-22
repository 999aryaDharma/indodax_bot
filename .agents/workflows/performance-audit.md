# performance-audit

**Goal:** Measure a bounded workload before proposing limits.

**Read:** `_BASELINE.md`, sprint/spec, host CPU/RAM/storage/GPU, representative snapshot, and concurrency assumptions.

**Steps:** Measure wall/CPU/RSS/disk/event lag or throughput; test bounded memory and interruption; preserve raw commands/results; propose versioned thresholds with uncertainty. Never infer production capacity from tiny fixtures.

**Output:** Workload identity, host, command/exits, measurements, variance, resource ceiling, and unresolved external gate.
