# Paper Research Release Candidate Evidence (REL-01)

## Overview
This document records the qualification evidence, verified gates, package manifest, and rollback runbook for the initial release candidate (`v0.1.0-rc1`) of the Indodax Research Lab.

## Release Metadata
- **Release Tag**: `v0.1.0-rc1`
- **Release Type**: Paper / Shadow Research Lab Candidate (CORE)
- **Execution Scope**: Academic research, offline backtesting, sealed evaluation, and paper forward simulation only. Real trading and withdrawals are strictly forbidden.

## Release Gates and Verification Matrix

| Gate | Requirement | Verification Artifact | Status |
|---|---|---|---|
| **Data Integrity** | Fixed cutoff, immutable parquet raw data, UTC-aware bars, no bfill | `tests/unit/lab/features/` & `tests/integration/lab/test_raw_to_silver_pipeline.py` | **PASSED** |
| **Accounting & Costs** | Decimal ledger, versioned fee/slippage schedule, conservative fill | `tests/unit/lab/backtest/` | **PASSED** |
| **Model Reproducibility** | Deterministic train-val split, Platt calibration, checksummed bundles | `tests/unit/lab/models/` | **PASSED** |
| **Tournament Checkpoint** | Offline multi-candidate evaluation, lifecycle outcomes (INVALID, HARD_FAIL, NEAR_MISS, PASS) | `tests/regression/test_wave1_tournament.py` (QA-01) | **PASSED** |
| **Boundary Security** | No live order/withdraw keys, path traversal blocked, pickle forbidden, Telegram allowlist enforced | `tests/security/test_lab_boundaries.py` (QA-02) | **PASSED** |
| **Capacity & Recovery** | Measured host profiles (Lenovo/Asus), disk-full atomic guard, idempotent metric replay ledger | `tests/integration/lab/test_operational_recovery.py` (QA-03) | **PASSED** |
| **Telegram Status** | Read-only research queue, champion and health reporting; chat allowlist | `tests/integration/lab/test_telegram_status.py` (REPORT-02) | **PASSED** |
| **Release Qualification** | Rollback integrity, experimental isolation, decoupled forward status | `tests/regression/test_release_candidate.py` (REL-01) | **PASSED** |

## Invariants and Operating Rules

1. **Rollback Plan & Proven Restoration (REL-01-AC1)**:
   - Rollback targets require matching SHA-256 artifact checksums in the target manifest.
   - Any corrupt or missing artifact aborts fail-closed with `RollbackIntegrityError`.
   - Reverting to previous compatible version (e.g. `v0.0.9`) restores state deterministically.

2. **Experimental Isolation (REL-01-AC2)**:
   - Candidates belonging to `EXPERIMENTAL` (e.g. RL spike R01-01) or `EXTENSION` (e.g. DL-01 neural worker) tiers cannot be silently promoted into release runtime.
   - `promote_candidate()` enforces `ExperimentalPromotionForbiddenError` unless explicitly approved by owner.

3. **Decoupled Champion Longevity (REL-01-AC3)**:
   - Software Release Candidate readiness (`software_rc_status="READY"`) is strictly decoupled from live forward longevity qualification.
   - Candidates lacking >=90 forward evaluation days or >=100 closed paper trades remain explicitly marked as `champion_status="PENDING_FORWARD_EVALUATION"`.

## Runbook
- Packaging command: `bash deploy/release-lab.sh v0.1.0-rc1`
- Test suite verification command: `pytest tests/`
