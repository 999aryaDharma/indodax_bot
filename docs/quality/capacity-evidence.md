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

## ASUS measured baseline - raw snapshot 2026-09-29 (UNVERIFIED, uncertified)

Collected read-only over SSH (`asus-server`, user kesawa) for QA-03 AC4/AC5, OPS-01 and JOB-02 AC4/AC5 evidence. Raw numbers only - no host is certified by this section.

- Host up 51 days; load avg 1.38/1.62/1.70; 4 CPUs (Intel i3-6006U 2C/4T @ 2.00GHz).
- RAM 3GB total / 1GB used / 1GB available (tight). Thermal zone0 63C at snapshot.
- Single physical disk sda 465.8G; LVM: / (98G, 75% used, 24G free), /srv/storage (295G, 1%), /var/lib/docker (49G, 1%), /boot (2G, 15%). All data mounts share one spindle - shared-disk contention applies (AC5).
- Co-resident load at snapshot: docker bimbel-staging/nextcloud/rbta stacks (healthy, weeks-old uptimes); no bot/trade/indodax/research service or container observed running.
- Still missing (needs soak/watch design): 24h mixed-load soak with preregistered budgets (AC4), mount-inventory/contention mapping against guard paths (AC5), 12h unattended incident qualification (AC6).

## ASUS 24h soak - collector running since 2026-09-29T15:50Z (IN PROGRESS, not evidence yet)

- Collector: `/tmp/qa03soak/collect.sh` on asus-server (PID 1243199 at launch, `nice -n 19`), 1 sample/min: timestamp, loadavg, mem total/avail, `/` avail KB, thermal mC -> `/tmp/qa03soak/soak.log` (~170KB/24h). No installs, no host changes besides /tmp scratch.
- Stop: `pkill -f collect.sh` (careful: self-matching pattern) or `kill <PID>`; fetch: `scp asus-server:/tmp/qa03soak/soak.log .`. First two samples sane (load ~0.7-0.9, mem avail ~1.7GB, thermal 45C).
- This soak alone does not satisfy AC4 (needs preregistered budgets + stepped pair-agent counts + representative co-resident Production/Research workload, none observed running) nor AC6 (12h unattended incidents).
