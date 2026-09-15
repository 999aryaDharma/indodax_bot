# SDD ledger — plan: docs/superpowers/plans/2026-09-15-audit-blocker-remediation.md

## 2026-09-15 continuation evidence

- Parent guarded combined regression for groups 1–3 completed with exit 0: **259 passed**. Command used `run_guarded_tests.py` over backtest/paper/golden, features/labels/DL sequence, training/feature materialization, artifact loader, backup/restore, queue, lifecycle, and operational recovery. Network was denied and a unique temporary directory was used.
- Full lab collection attempt: exit 0, **649 tests collected**. This is collection evidence only, not execution.
- `git diff --check` completed with exit 0; only LF/CRLF advisory warnings. A stale inaccessible `.pytest-tmp/group3-backup-20260915-002` directory produced a permission warning during status/diff inspection and was not removed.
- Group 3 latest report records its earlier 54-pass/4-fail intermediate gate and subsequent fixes for Windows writable-handle fsync, privilege-free junction confinement test, and truthful recovery qualification. The final 259-pass parent gate covers those paths.
- Independent review requirement remains open: all three reviewer agents hit usage limits before returning review findings. Parent has not fabricated independent approval. Groups 1–3 therefore remain review-pending despite the green combined test gate.
- Current scope remains blocked by groups 4–5 planning defects (RL/foundation/graph/LOB evidence and corrupted manifest/dependency governance), missing independent review, unavailable ruff, and known research-label proxy alignment gap (`promotion_eligible=False`).
- Follow-up safe correction: `AllocationBaselineComparator.allocate_cash` now validates simplex weights and rounds Decimal allocations down, preventing equal-weight rounding from overspending capital. Added regression in `tests/research/test_rl_reward_contract.py`; result **4 passed**. This does not validate RL profitability or promote the model.
- RL truthfulness correction: `RLFeasibilityReport` no longer emits fabricated Sharpe values or a positive net-cost evaluation claim. It reports `UNEVALUATED`, `INCONCLUSIVE`, and nullable Sharpe fields until a deterministic offline evaluator supplies immutable evidence. Focused model gate after this change: **20 passed** across RL, foundation, graph, and LOB contract tests.
- Remaining group-4 evidence is still open: graph ranker initializes random weights and foundation/LOB capabilities need explicit backend/archive/coverage qualification before any promotion claim. These were not silently marked complete.
- Public-data fetch validation: added `eth_idr` venue mapping and credential-free HTTP headers. One-month 1h windows (2021-01-01 through 2021-02-01) fetched successfully into ignored `lab-data-fetch2`: BTC/IDR 744 accepted + 1 outside-window reject; ETH/IDR 744 accepted + 1 outside-window reject; both HTTP 200 with raw wire, manifests, checkpoints and hashes. Windows fixes were required for directory fsync portability and colon-containing snapshot IDs. Full-range backfill remains pending until the environment's pytest-temp permission issue is isolated and the fetch pipeline is regression-tested.
- Five-year public backfill completed in immutable monthly windows: BTC/IDR 60 checkpoints in `lab-data-fetch2`, 43,824 accepted rows; ETH/IDR 60 checkpoints in `lab-data-eth-final`, 43,824 accepted rows. Both cover 2021-01-01 through 2026-01-01 at 1h. Each month reported one out-of-window row rejected by the parser. An earlier ETH root encountered an immutable byte conflict for a repeated September 2025 request; it was preserved and isolated rather than overwritten. Backfill production modules compile successfully and pass diff-check; pytest data tests remain environment-blocked by global temp-directory permission.
- Scalping 5m fetch: BTC/IDR completed 60 monthly checkpoints in `lab-data-5m` (2021-01-01–2026-01-01). ETH/IDR has partial checkpoints in that root but hit an immutable byte conflict for a repeated June 2022 request; no overwrite was performed. SOL/IDR had no accepted rows in January 2021 (listing/data unavailable) and one validated January 2025 window in `lab-data-5m-sol` with 8,928 accepted + 1 rejected row. SOL must use a point-in-time listing start, not be backfilled from 2021 blindly.
- Official Indodax references found via web search state SOL/IDR listing began 11 November 2021 ([Indodax Academy listing reference](https://indodax.com/academy/pimpin-pasar-kripto-awal-februari-cek-harga-solana-di-sini/)). SOL 5m backfill therefore starts at 2021-11-11; initial two windows through 2022-01-01 produced 14,625 accepted + 2 rejected rows. ETH retry in `lab-data-5m-eth-final` remains partial and stops fail-closed on repeated immutable byte conflicts; no raw data was overwritten.
- New read-only automation: `python -m indodax_lab.cli.dataset_inventory <roots...>` verifies every manifest partition SHA-256, counts checkpoints/rows/rejects by pair and interval, prints JSON, and exits 2 on integrity errors. Inventory over `lab-data-fetch2`, `lab-data-eth-final`, `lab-data-5m`, and `lab-data-5m-sol` returned PASS with no integrity errors. It confirms `lab-data-5m` currently contains both BTC/IDR and ETH/IDR complete five-year coverage (525,888 accepted rows each); the earlier ETH conflict is preserved in the separate retry root.

Baseline: dev / 0c788c0d432eb67440c9fdfb41b2e9f21ada4f41 plus existing uncommitted accounting and temporal corrections.

## Preflight

| Task / pair | Check | Resolution |
| --- | --- | --- |
| 1 | Tests and design require fee-inclusive admission, safe exits and causal marks | Consistent; preserve prior ledger patch |
| 2 | Tests and design require source availability, identities and role segmentation | Consistent; preserve prior AUD-008 patch |
| 3 | Tests and design require complete hashes, atomic active view and bounded leases | Consistent; reject unsupported lifecycle instead of claiming fake success |
| 4 | Missing genuine model evidence cannot be repaired by inventing training | Plan only; explicit unevaluated gate before new research |
| 5 | Manifest/dependencies shared and user requirements dirty | Plan only; one coordinator writer; no changes this wave |
| 6 | Full-suite and reviewer gates vs incomplete environment | Attempt and report actual failure; no blanket PASS |
| 1 ↔ 2 | MarketBar/SignalIntent inputs and label/source chronology | Group 1 owns event models; group 2 reads and coordinates signature changes |
| 1 ↔ 3 | Ledger/judge consumes local artifacts, no shared file ownership | Group 3 never edits ledger; root verifies regression |
| 2 ↔ 3 | Training identities versus portable bundle metadata | Group 2 owns dataset hashing; group 3 owns bundle serialization; each preserves public inputs |
| 3 ↔ 4 | Bundle validation and model loaders | Group 4 implementation deferred until bundle contract stabilized |
| 1–3 ↔ 5 | Dependency/manifest/package exports | Implementers cannot modify shared dependency/manifest files |

User-selected execution: three implementers parallel on current dev, with exclusive paths rather than separate worktrees. No commits or cleanup; reports retained. These user instructions supersede generic sequential/worktree/commit/cleanup skill steps.

## Claims

- Task 1: RUNNING — `/root/group1_judge_fix`; backtest, paper/portfolio, owning tests.
- Task 2: RUNNING — `/root/group2_temporal_fix`; features, labels, models/dl/dataset, owning tests.
- Task 3: RUNNING — `/root/label_temporal_fix_review` reassigned as implementer; models/artifacts, operations, queue, owning tests/deploy entries. A third new thread was refused by platform thread limit; a completed independent task seat was reused. This agent cannot final-review its own group 3 implementation.
- Task 4: PLANNED only.
- Task 5: PLANNED only.
- Task 6: coordinator; independent reviewers assigned after implementation.

## Verification and review

Implementation and review evidence will be appended as commands finish. No task is complete at plan creation. Manifest remains invalid and unchanged; no sprint status update.

Planning helper initially failed with Git Bash signal-pipe Win32 error 5 in sandbox. Approved retry succeeded: three scoped task briefs created under `.superpowers/sdd/2026-09-15-audit-blocker-remediation/`. Reports and working-diff review packages will remain there; durable evidence summaries stay in this ledger/handoffs.

Read-only group 5 planning evidence: all 18 revisions of sprint-manifest.json available in local Git failed JSON parsing, including initial introduction 9d9e610. Planning validator still raises JSONDecodeError line 1. Manifest reconstruction remains a future task; no file modified. Current CI installs dev/research on Python3.11 but does not install optional Torch; requirements-dl contains torch>=2.0.0 only. No package compatibility claim or dependency installation performed.

Group 1 interface notice: MarketBar gains explicit causal liquidity evidence; simulator signature remains simulate_execution(intent, bar). Taker cannot use outcome volume; engine may pass a disclosed prior-closed-volume proxy. Group 2 was notified and keeps strict feature DataFrame source metadata with no fallback.

Implementation progress (reports, not final qualification): group 1 reported 21 behavioral RED failures/1 pass, followed by 35 new+preserved accounting cases passing. Group 2 is adding source-delay/gap/context/hash/sequence negative cases. Group 3 selected full canonical bundle hashes, immutable transfer versions + single active-reference switch, lease expiry/budget fencing, OS-backed local writer lock and injected-or-unsupported lifecycle.
