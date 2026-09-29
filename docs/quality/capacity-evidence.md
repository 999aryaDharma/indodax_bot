# Host Capacity and Crash Recovery Evidence (QA-03)

> Evidence qualification, 2026-09-24: the historical statements below do not certify co-resident ASUS Production + WebSocket + multi-strategy shadow capacity. OPS-01/QA-03 remain REVIEW. See [current cross-check](../implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md); new mixed-load measurements are pending.

## Host Qualification Summary
This document records host capacity evidence, crash survival mechanisms, and
storage recovery behavior for the Indodax Research Lab release candidate. No
host is certified by this document: every profile below is UNVERIFIED pending a
measured artifact from the target host (24h mixed-load soak, mount inventory).

## Empirical Host Profile Benchmarks

| Host Profile | Max Workers | Memory Allocation | Storage Root | Role | Measured Baseline |
|---|---|---|---|---|---|
| **LenovoThinkPad** | 2 workers | 4,096 MB | `/var/data/indodax_lab` | Background ML trainer & shadow trader | **UNVERIFIED (pending measured artifact)** |
| **AsusZenBook** | 4 workers | 8,192 MB | `/var/data/indodax_lab` | Research batch evaluator & pipeline | **UNVERIFIED (pending measured artifact)** |

## Invariants and Verified Failure Behaviors

1. **Storage Exhaustion Guard (QA-03-AC1)**:
   - Atomic writes utilize `DiskGuardWriter` with explicit pre-flight free space checks.
   - If available space is below safety threshold (`min_free_bytes`), the write immediately aborts fail-closed with `DiskFullError`.
   - Incomplete or corrupted files are purged; the system never returns a false positive success state.

2. **Crash & Worker Kill Replay Recovery (QA-03-AC2)**:
   - When background compute workers crash, receive `SIGKILL`, or are unexpectedly terminated, execution resumption occurs without metric duplication.
   - `IdempotentMetricLedger` indexes entries by `(run_id, metric_name, fold_idx)`, safely ignoring duplicate metric submissions from replayed tasks.

3. **Empirical Resource Ceiling Enforcement (QA-03-AC3)**:
   - Capacity ceilings are derived exclusively from measured empirical run benchmarks, never from raw logical CPU core counts.
   - `EmpiricalHostCapacityValidator` rejects unbenchmarked host profiles (`UNBENCHMARKED_HOST`) and blocks workloads that exceed empirical memory/worker limits (`CAPACITY_CEILING_EXCEEDED`).

## Test Evidence
- Test suite: `tests/integration/lab/test_operational_recovery.py`
- All 4 tests pass with 100% assertion coverage. These are synthetic,
  fixture-based probes only: they exercise the guard/ledger/validator
  mechanisms, not a measured host. They do not constitute host qualification.
