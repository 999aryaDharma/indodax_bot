# Audit Blocker Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. User explicitly authorizes parallel implementation of groups 1–3 on the existing `dev` checkout with exclusive file ownership. Groups 4–5 are planning only this wave; group 6 qualifies this wave, not a complete release.

**Goal:** Close the remaining verified audit defects without expanding the paper/shadow research scope or inventing evidence.

**Architecture:** Keep the existing domain layers. Strategies emit intent; the judge alone sizes, fills, charges costs and journals equity. Feature/dataset transformations own causality and identity; artifact/operations boundaries own integrity, transactional publication and recovery. Invalid or unsupported paths fail closed with explicit diagnostics.

**Tech Stack:** Existing Python, Decimal, pandas/NumPy, Pydantic, SQLite and immutable local files; optional Torch only inside DL worker paths. No added service or dependency in this wave.

**Spec:** `docs/specs/00-master-product-technical-spec.md`, accepted ADR-002 and ADR-003, `docs/specs/09-labels-splits-and-training-data.md`, `docs/specs/20-testing-strategy.md`, owning sprint Required Reading, and `docs/research/dataset-feature-contracts.md` (ADR-002 overrides old availability wording).

## Global Constraints

- `available_at <= decision_ts`; closed bars only; fitted statistics use authorized train data; mutation future input leaves past output invariant.
- Decimal/integer money, separate quantities and valuation; journal balances; no duplicate fee deduction.
- Atomic publication with file and directory fsync where supported; failed/indeterminate result never treated as success.
- No real trading credentials; safe local paths/artifact loaders; chat allowlist; secret redaction; untrusted content cannot become code.
- Checkpoints after durable artifacts; idempotent restart; backup restore rehearsed; no stale-worker publication.
- No live orders, withdrawals, leverage, shorts, futures, martingale, LLM execution, auto-merge or scheduler activation.
- Preserve existing uncommitted accounting/temporal fixes. Preserve `requirements.txt` exactly: SHA256 `01e97526e4b9fd5ef2110aa308609ea70dad0d6084335ea55ad27d53b9f9630c`.
- No commit, push, destructive cleanup or manifest/status mutation by implementers. No real runtime databases in tests. Temp paths are unique; do not remove previous evidence.
- Source baseline HEAD `0c788c0d432eb67440c9fdfb41b2e9f21ada4f41`, branch `dev`. Starting working diff is part of the baseline, not permission to overwrite it.
- Manifest is currently invalid JSON; no READY/DONE claim is made. These are user-authorized defect corrections, not new sprint capability admission.

## Scope and dependency map

| Group | Audit IDs / capability | Owns writes | Read-only cross-boundaries | Execution |
| --- | --- | --- | --- | --- |
| 1 Judge/risk/accounting | AUD-001 residual, AUD-002–005; SIM/LED/SHADOW | `src/indodax_lab/backtest/`, `src/indodax_lab/paper/portfolio.py`, matching backtest/paper tests | costs/schedule public contract, features only as input | Parallel now |
| 2 Temporal/datasets | AUD-006–010; FEAT/LABEL/SPLIT/TRAIN/DL-02 | `src/indodax_lab/features/`, `labels/`, `models/dl/dataset.py`, corresponding feature/label/sequence tests | Group 1 event classes; group 3 bundle formats | Parallel now |
| 3 Artifacts/recovery/operations | AUD-011–014, AUD-020; ART/JOB/OPS | `models/artifacts.py`, `operations/`, `orchestration/queue.py`, necessary queue types, corresponding artifact/queue/operations tests, `deploy/` if disabling broken launch entries | Group 2 training metadata, group 1 ledger | Parallel now |
| 4 Model/LOB claims | AUD-015–019; R01/G01/F01/LOB/L01/L02 | RL, graph, foundation, LOB modules and their own tests/research reports | Requires stable 1–3 interfaces before integration | Plan only |
| 5 Planning/environment | AUD-021–023; governance/CI | Manifest/projections, dependency files, pyproject, CI, planning evidence | Reads all reports and actual Git provenance | Plan only; coordinator-owned |
| 6 Qualification | Cross-group integration, safety and independent review | Coordinator-owned evidence and regression runner only | Reads complete patch; never self-approves | After groups 1–3 |

Group 2 owns only `models/dl/dataset.py`, not bundle serialization. Group 3 owns `models/artifacts.py`, not training dataset IDs. Cross-group imports/signature changes must be messaged to the coordinator before editing a consumer outside ownership. No two implementers edit a shared test or package initializer.

## Task 1: Judge, risk and accounting (implement now)

**Files:** `src/indodax_lab/backtest/{events,execution,engine,risk,ledger}.py`, `src/indodax_lab/paper/portfolio.py`; `tests/unit/lab/backtest/`, shared reconciliation tests, `tests/integration/lab/test_backtest_golden.py`.

**Interfaces:** Preserve `SignalIntent`, `MarketBar`, `ExecutionResult`, `PortfolioRiskManager.assess_order`, `ResearchLedger.process_fill` and `ReplayBacktestEngine.run`. Add explicit optional causal liquidity evidence if needed; missing evidence must not become perfect fill. Coordinate changes to MarketBar with group 2. Preserve existing positive-finite paper validation and staged ledger writes.

### 1A Cash reservations and execution-time admission

- [ ] RED: two pending BUY intents that each fit cash separately must not jointly overdraw; fill gap-up plus fees must not overdraw; existing 20% position cannot add another 20%; invalid leverage/fractions fail closed.
- [ ] GREEN: reserve admitted pending notional plus estimated fees; release reservations on fill/reject/cancel, exactly once. Recheck current inventory, other reservations, equity and actual fee-inclusive fill debit before posting. Downsize only with quantity precision/minimum preserved, otherwise reject with reason; never round an invalid minimum upward.
- [ ] Keep journal atomic. Reject malformed initial balances, invalid marks and fees before state changes. Guard concurrent in-process shared allocation if the same ledger object is used concurrently; do not claim a process lock from a thread lock.

Core acceptance arithmetic (literal fixture expected values):

```python
assert cash_after_rejected_buy == Decimal("1000")  # gross1000 + fee10 cannot spend cash1000
assert additional_notional_at_existing_cap == Decimal("0")
assert sum(reservations.values()) <= available_cash
```

### 1B Independent exits and causal simulation

- [ ] RED: held position hits stop while strategy returns None; halt must still allow reducing exposure; both stop and target touched must follow SL_FIRST; two open pairs must mark without missing-mark crash.
- [ ] GREEN: judge retains entry risk parameters, monitors on every eligible market event, schedules/executes conservative exits without needing another strategy entry intent. Entry-halted state rejects added risk, not safe reductions. Do not credit a stop fill before data establishing the stop was available.
- [ ] RED: perturb next candle high/low/volume and assert no change in a fill already recorded at its open; repeated run on the same engine must not inherit cash/inventory/processed IDs.
- [ ] GREEN: separate open-time decisions from completed-bar observations. Taker next-open uses only liquidity available then; maker bar-touch evidence cannot be backdated to open. Use prior closed liquidity or explicitly timestamp deferred bar-evidence fills at their availability. No invented L2 queue priority. Maintain causal marks for every held pair; enforce chronological event order and no future other-pair marks. Reset per-run state or reject engine reuse explicitly.
- [ ] Bind replay identity to disclosed execution-fidelity version and complete valued transaction identity (pair, quantity, timestamps, postings), so a new causal proxy cannot be mistaken for the old simulator output.

```python
assert fill_using_bar_touch.timestamp >= outcome_bar.close_time
assert buy_halted.approved is False
assert risk_reducing_sell.approved is True
assert replay_a.postings_hash == replay_b.postings_hash
```

- [ ] Run focused RED/GREEN per subcase, then `python -B -m pytest tests/unit/lab/backtest tests/unit/lab/paper tests/integration/lab/test_backtest_golden.py -q -p no:cacheprovider` with unique temp roots and network guard.
- [ ] Report exact paths, command/exits, causal timing decisions and remaining limits. Hand off without committing; independent review is required.

## Task 2: Temporal features and verified datasets (implement now)

**Files:** `src/indodax_lab/features/{builder,context,registry,technical,liquidity}.py` only as needed; `src/indodax_lab/labels/{materializer,splits,returns}.py`; `src/indodax_lab/models/dl/dataset.py`. Tests in features/labels, sequence dataset unit test and feature/training integration tests. Preserve the preceding AUD-008 fixes and its 42 focused passing cases.

**Interfaces:** `build_feature_frame`, `point_in_time_market_context`, `asof_join_features`, `materialize_training_dataset`, `assign_folds`, `CausalSequenceBuilder.build`; public tables retain sample IDs, explicit UTC times, eligibility/reason and role evidence. Expose additive metadata with a version transition; reject legacy missing evidence rather than silently filling it.

### 2A Feature source availability and context

- [ ] RED: delayed source inside rolling window; gap resetting warmup; infinity; missing closed/availability fields; BTC series different from target asset; both feature/universe frames containing eligible columns.
- [ ] GREEN: compute readiness from every observation required by a feature (conservative historical maximum is acceptable only if recorded, no false eligibility). Require closed UTC data, strictly chronological pair/session windows and gap resets. Warmup is observed usable history, not merely row count. Invalid finite values become ineligible with reason, never bfill/zero substitution.
- [ ] Align BTC inputs by source availability, not row index or target close series. Reject/mask missing BTC context. Distinguish feature and universe eligibility columns before joins; propagate universe availability and membership. No full-sample universe normalization.

```python
assert delayed_row.eligible is False
assert delayed_row.row_ready_at >= delayed_source.available_at
assert missing_btc_row.eligible is False
assert first_row_after_gap.eligible is False
```

### 2B Dataset identity and contract validation

- [ ] RED: changing one label, split role, feature order, cost ID, or byte checksum must change identity or fail verification; reordered equivalent logical rows must be deterministic; missing/null sample IDs and incomplete joins rejected.
- [ ] GREEN: version content hashing and bind validated feature/label contents, ordered inference features, split assignments/policy/boundaries, cost ID and parent identities. Exclude ambient creation clock and absolute paths. Verify caller-supplied checksums and always compute content digests even if no expected hash supplied. Old IDs are not upgraded in place; output new identity domain/version and document rebuild-only transition.
- [ ] Preserve prior mandatory availability and cutoff validation. Verify finite eligible inputs, actual inference column existence/uniqueness and role counts. Distinct immutable logical inputs must never reuse current row-count-only identity.

```python
assert original.manifest.dataset_id != changed_target.manifest.dataset_id
assert original.manifest.dataset_id != changed_cost.manifest.dataset_id
assert original.manifest.dataset_id == reordered_equivalent.manifest.dataset_id
```

### 2C DL causal sequence boundaries

- [ ] RED: TRAIN/SEALED_TEST/TRAIN adjacent rows cannot form one window; renamed future_return must not enter X; delayed feature or nonfinite value must not enter an eligible batch.
- [ ] GREEN: validate explicit feature allowlist against prohibited target/outcome names, UTC readiness, finite values and positive sequence config. Partition by pair, session/gap and role/fold before rolling. Preserve masks and target separation; no sequence crosses an unauthorized role. Missing role/readiness must be explicit rejection, not default TRAIN. Do not import Torch until requested.

```python
assert all(len(set(window_roles)) == 1 for window_roles in accepted_window_roles)
assert "future_return" not in inference_columns
assert not batch.X.flags.writeable  # if exposing arrays as immutable artifact data
```

- [ ] Run focused RED/GREEN per case, then feature/label/sequence and training integration regression; coordinate consumer fixture changes rather than editing group 1/3 files.
- [ ] Report temporal assumptions, new hash domain/schema, rebuild policy, exact evidence and open gaps. No commit or DONE transition.

## Task 3: Artifact integrity, recovery and operations (implement now)

**Files:** `src/indodax_lab/models/artifacts.py`, `src/indodax_lab/operations/{staging,restore,backup,recovery,service_lifecycle}.py`, `src/indodax_lab/orchestration/queue.py` and queue type validation as required. Own artifact, staging, recovery, queue and service tests; no DL dataset or training materializer edits. `deploy/` only for disabling false/nonexistent launch targets, not adding activated services.

**Interfaces:** `PortableBundle.to_bytes`, `PortableBundleLoader.load_from_bytes`, `verify_bundle`, `stage_and_publish_transfer`, `SqliteJobQueue.claim_job/heartbeat/complete_job`, `SingleWriterLock`, `ManagedService`. Preserve explicit failure/result types where possible; document safe incompatible artifact revisions.

### 3A Complete bundle integrity

- [ ] RED: mutate calibration, preprocessing, feature order, version or provenance while retaining recorded hash; loader must reject. A clean serialize/load round trip must preserve predictions.
- [ ] GREEN: canonical full payload identity excluding only its own hash; all inference-affecting metadata participates. Recompute before constructing usable objects. Validate finite numeric parameters and explicit supported schema; never deserialize external pickle. Unverified legacy bundle cannot silently qualify as new validated bundle.

```python
with pytest.raises(ValueError):
    PortableBundleLoader().load_from_bytes(tampered_payload)
assert loaded.predict_proba(X).tolist() == original.predict_proba(X).tolist()
```

### 3B Safe, atomic transfer

- [ ] RED: ../ traversal, absolute/drive paths, symlink escape and duplicate normalized targets; no writes may escape destination. Inject failure on the second publish operation; the active view must still reference the entire old bundle, not a mix.
- [ ] GREEN: validate all source/destination paths and manifest members before writing. Prefer immutable version directory plus one atomic active-reference switch if compatible; otherwise reject overwrite of active roots and use a documented transactional mechanism. Never call sequential per-file replacements an atomic multi-file publish. Check bytes/hashes before promotion; keep failed staging evidence non-active and retry-idempotent. Coordinate consumers if return path changes.
- [ ] Preserve fsync ordering where supported. Windows unsupported directory fsync must be platform-scoped and documented, not a blanket exception suppressor for genuine I/O failures.

```python
assert outside_file.exists() is False
assert active_manifest_after_failed_publish == old_manifest
assert retry_result.manifest_hash == first_success.manifest_hash
```

### 3C Queue and real lifecycle boundaries

- [ ] RED: max_attempts=1 then expired RUNNING/STALE/PENDING must not allow attempt2; stale worker cannot heartbeat/complete after lease expiry/reclaim. Verify transactional claims on separate SQLite connections.
- [ ] GREEN: apply attempt cap to every claimable state, exhaust terminally and fence with lease token/owner/version in the same transaction. Retry admission cannot be reset by changing state or worker ID. Test rollback on failure and foreign-key settings per connection where relevant.
- [ ] RED: independent SingleWriterLock instances with identical resource ID cannot both acquire; process death must not leave a permanent ownership lie. ManagedService without actual lifecycle hooks must not claim successful process start or flush.
- [ ] GREEN: cross-process OS-backed local lock (single-host semantics), safe lock path, ownership checked on release; recovery after process exit. Lifecycle uses injected concrete start/stop/flush evidence or explicitly unsupported fail-closed mode. No background process activation in this task; controlled fake hooks/child probes only in tests. Broken deploy entry points are not declared operational.

```python
assert queue.claim_job("second", as_of=after_expiry) is None  # exhausted budget
with pytest.raises(ConcurrentWriterLockError):
    second_lock.acquire("other")
assert unsupported_service.is_flushed is False
```

- [ ] Run targeted behavior RED/GREEN, multi-file failure injection and multiprocess lock tests using unique temp paths. Run owning integration tests once after implementation. Report platform durability limitations and exact evidence; no cleanup of old evidence, commits or service activation.

## Task 4: Model and LOB truthfulness (plan only)

**Files:** `models/r01_rl_allocator.py`, `models/graph/g01_cross_asset.py`, `models/foundation/{f01_kronos,provenance}.py`, `models/lob/{dataset,l01_deeplob,l02_tlob}.py`, matching tests and `docs/research/` evidence.

**Solving strategy:** Do not replace fabricated evidence with a new unapproved training project. Missing genuine backend, data or evaluation must return UNIMPLEMENTED/UNEVALUATED/BLOCKED and cannot be promoted. Real implementation proceeds only within existing sprint external gates.

- [ ] RL: replace hardcoded net-cost/Sharpe claims with explicit unevaluated result unless an actual deterministic offline evaluator exists. Charge fee once, enforce simplex/no-short/no-leverage; Decimal down-round and allocate remainder so six equal weights cannot spend 500100 from 500000. Preserve forbidden policy export and absence of scheduler.
- [ ] Foundation: remove row-count-only probability cache; always apply the fitted adaptation pipeline to the actual input. Require verified weights/provenance and declared supported backend before calling output foundation-model evidence. Do not download or execute unknown weights.
- [ ] Graph: a random projection is not a trained GNN; a copied momentum column is not OLS. Explicitly distinguish baseline adapters from unimplemented model capability. Preserve historical reports but append corrections.
- [ ] LOB: count actual contiguous PASS interval coverage, not 90 one-second sessions labeled 90 days. Validate pair/session/event ordering, availability, gaps and effective event counts. Archive outcomes durably before reporting evidence preserved; evaluator remains promotion authority; trial budget must count admitted configurations across instances/restarts.

Tests/solving invariants:

```python
assert sum(decimal_allocations) <= Decimal("500000")
assert different_X_same_length_changes_predictions
assert tiny_daily_sessions_are_not_90_day_coverage
assert new_instance_can_read_archived_trial
assert missing_verified_backend_report.status == "BLOCKED"
```

Verification uses owning model unit tests plus offline integration, optional DL environment only. Acceptance requires negative gates and honest missing capability, not profitable backtests. Depends on group 2 split/feature and group 3 artifact/registry contract stabilization.

## Task 5: Planning and reproducible environment (plan only)

**Files:** `docs/sprints/sprint-manifest.json`, `SPRINT-STATUS.md`, feature/index projections, handoff corrections, `requirements*.txt`, `pyproject.toml`, `.github/workflows/ci.yml`.

- [ ] Recover a complete manifest from valid Git history plus all 92 sprint specs; never strip only the corrupt header because a middle chunk is also missing. Cross-check DAG, accepted dependencies and handoffs. Historical Tasks1–14 retain qualified historical provenance; fresh work remains REVIEW/BLOCKED until exact evidence permits promotion. Missing specs 22/23 require authoritative source discovery, not invented text.

  Preflight evidence: all 18 local revisions returned by `git rev-list --all -- docs/sprints/sprint-manifest.json` are invalid JSON, including first introduction `9d9e610`. There is no verified intact local version to restore. Reconstruction must use complete sprint spec metadata/DAG plus handoff provenance; unresolved conflicts remain BLOCKED. Remote recovery requires explicit source verification, not assuming a cached branch is newer.
- [ ] Correct Gemini's claims through evidence addenda, preserving original reports. A ModuleNotFoundError is environment failure, not behavioral TDD RED. No fabricated independent reviewer or all-DONE status.
- [ ] Preserve user's dependency edits. Propose an explicit merge of needed runtime dependencies and isolated environment; obtain any necessary network/install permission. Verify Python compatibility against actual package metadata before changing pins.
- [ ] Separate light core and optional DL CI, register markers and ensure missing optional libraries cannot silently skip required acceptance. Add actual dependency/install, collection, lint and full-suite checks per profile. Format only owned changes; don't sweep legacy code.

Commands after recovery: `python docs/quality/validate_planning.py`, `python -m pytest -q`, `python -m ruff check src tests`, `git diff --check`. Record actual exit/status; no PASS from unavailable tools. No runtime activation is part of environment repair.

## Task 6: Integration and independent review (qualify current wave)

**Owner:** coordinator, with independent reviewers after implementers release their file claims.

- [ ] Read each report, inspect exclusive paths and resolve signature changes against spec. Generate review packages and dispatch task-specific reviewers (spec AND quality); max five rounds, preserve round counters and unresolved findings.
- [ ] Execute all targeted regressions together with forced fake credentials, network denied, `-B`, no pytest cache and unique retained temp roots. Use `C:/Users/User/miniconda3/envs/ML/python.exe` currently available. Root owns the full-suite attempt, avoiding three simultaneous heavy suites.
- [ ] Attempt full suite because judge/shared contracts changed; currently pandas_ta collection and optional runtime packages are known blockers. Attempt lint; currently ruff unavailable. Report these as blocked, not PASS. Compile changed Python in memory and run diff-check.
- [ ] Broad independent cross-group review includes adapters: feature readiness→intent, intent→execution→ledger, dataset→bundle, staging→restore, queue lease→publish. It must not confuse scoped remediation with all historical branch acceptance.
- [ ] Publish exact command/exit, tests, source baseline plus working-diff identity, unresolved findings and implementation limits. Keep branch BLOCKED if Important gaps or missing required verification remain. No automatic commit, merge, manifest DONE, push or release.

## Preflight and execution record

The coordinator keeps `docs/quality/2026-09-15-remediation-progress.md`: file claims, preflight interface pairs, implementation/review states, evidence and residual risks. This durable checked-in-path ledger is retained rather than deleted, per the user's preservation/audit requirements. No broad worktree cleanup.

Self-review: groups 1–3 own disjoint source trees except explicit adapters; all adapter changes require coordinator approval. Tasks 4–5 are future implementation plans, not admission to execute them now. Group 6 may run safe diagnostics but not alter dependencies to manufacture PASS.
