# LOB-01 handoff

Status: DONE

## Identity
- Sprint ID: LOB-01 — Forward book dataset eligibility
- Implementation agent: Antigravity (original); Codex `/root` (review remediation)
- Independent reviewer: `/root/cost01_independent_review` (PASS on exact final code SHA)
- Branch / worktree: `feat/feat-02-finalization` (user-authorized continuation in current worktree; original implementation target `feat/lob-01-forward-book-dataset-eligibility`)
- Base SHA: `f9930c6`
- Code target: `72c72ce09afe7a21c0d8c11872367c7d27f72783` (`fix(lob-01): break windows at sequence gaps`), based on original target `e7e1b098732db79e98d6956e92096cd16c6e7bc3`
- Evidence SHA relation: `72c72ce`

## Files and contracts
- Planned files:
  - `src/indodax_lab/features/lob.py` (extract_lob_tensor, compute_depth_imbalance, compute_spread, compute_microprice)
  - `src/indodax_lab/models/lob/dataset.py` (LOBDatasetEligibilityGate, BookSnapshot, BookLevel, LOBSessionMetadata, LOBEligibilityReport, CandleSubstitutionForbiddenError, SessionGapBrokenWindowError, InsufficientCoverageGateError)
  - `src/indodax_lab/models/lob/__init__.py`
  - `tests/unit/lab/models/lob/test_lob_data_gate.py` (AC0..AC3 test cases)
- Contract:
  - `continuous raw books -> depth/imbalance tensors with >=90 day coverage gate plus sample/regime report`
  - Dataset eligibility gate: Sessions require >=90 distinct calendar days with PASS status and sufficient effective events to pass the gate and produce an eligibility report (LOB-01-AC0).
  - Candle substitution prohibition: Any OHLCV candle dataframe or dictionary attempting to substitute for order book depth snapshots is rejected fail-closed with `CandleSubstitutionForbiddenError` (LOB-01-AC1).
  - Gap breaking: Sequence windows strictly segment upon encountering gaps exceeding `max_gap_seconds` (e.g. 10s or 60s); sequence windows never bridge or interpolate across unobserved intervals (LOB-01-AC2).
  - Calendar coverage enforcement: High row counts concentrated across fewer than 90 calendar days are rejected fail-closed with `InsufficientCoverageGateError` (LOB-01-AC3).
- Review remediation contract: each pair independently satisfies the configured distinct PASS-day minimum; every represented pair/day meets the configured event floor; windows split at pair/session, time-gap, and sequence-gap boundaries and reject timestamp/sequence regressions; snapshots require non-empty, correctly ordered, non-crossed depth and a session ID.
- Migration and compatibility:
  - The additive LOB package now requires `session_id` on `BookSnapshot`; in-repository L01/L02 fixtures were updated. Consumers outside the repository must supply source book-session identity before adopting this contract.
  - Dependencies: DATA-06 (DONE), FEAT-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| LOB-01-AC0 (RED) | `test_lob_01_valid_contract` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.lob') | `working tree` |
| LOB-01-AC0 (GREEN) | `test_lob_01_valid_contract` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_valid_contract` | Exit 0 (Passed, 92-day PASS sessions pass gate, generate depth/imbalance tensors and regime report) | `e7e1b09` |
| LOB-01-AC1 (RED) | `test_lob_01_contract_1` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| LOB-01-AC1 (GREEN) | `test_lob_01_contract_1` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_contract_1` | Exit 0 (Passed, candle OHLCV data rejected with CandleSubstitutionForbiddenError) | `e7e1b09` |
| LOB-01-AC2 (RED) | `test_lob_01_contract_2` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| LOB-01-AC2 (GREEN) | `test_lob_01_contract_2` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_contract_2` | Exit 0 (Passed, 120s gap breaks sequence window into non-overlapping runs without interpolation) | `e7e1b09` |
| LOB-01-AC3 (RED) | `test_lob_01_contract_3` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| LOB-01-AC3 (GREEN) | `test_lob_01_contract_3` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_contract_3` | Exit 0 (Passed, 1,000,000 events in 15 days fails 90-day coverage gate fail-closed) | `e7e1b09` |
| Review regression | `test_coverage_requires_minimum_events_on_each_day_and_pair`, `test_windows_split_at_pair_session_and_sequence_boundaries`, `test_book_snapshot_rejects_invalid_depth` | `$env:PYTHONPATH='src'; C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/models/lob tests/integration/lab/test_deeplob_smoke.py tests/integration/lab/test_tlob_smoke.py -q -p no:cacheprovider` | Exit 0, 17 passed | `72c72ce09afe7a21c0d8c11872367c7d27f72783` |
| Ruff focused correctness rules | changed LOB files (`E4,E7,E9,F821,F823,B905`) | `C:\Users\User\miniconda3\envs\ML\Scripts\ruff.exe check --select E4,E7,E9,F821,F823,B905 src/indodax_lab/models/lob/dataset.py tests/unit/lab/models/lob/test_lob_data_gate.py tests/integration/lab/test_deeplob_smoke.py tests/integration/lab/test_tlob_smoke.py` | Exit 0, All checks passed | `72c72ce09afe7a21c0d8c11872367c7d27f72783` |
| Reviewer focused check | `test_lob_data_gate.py` | `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py -q -p no:cacheprovider --basetemp C:\Users\User\AppData\Local\Temp\lob01-review-72c72` | Exit 0, 9 passed | `72c72ce09afe7a21c0d8c11872367c7d27f72783` |
| Full suite | repository tests | `$env:PYTHONPATH='src'; C:\Users\User\miniconda3\envs\ML\python.exe -m pytest -q -p no:cacheprovider` | Exit 0, 1014 passed, 2 platform-specific skipped, 3 existing sklearn OptimizeWarnings (55.75s) | `72c72ce09afe7a21c0d8c11872367c7d27f72783` |

Initial implementation tests above are retained as provenance only; the exact remediation SHA was verified by the newer commands above.

## Review
- Initial independent review on `e7e1b098732db79e98d6956e92096cd16c6e7bc3`: CHANGES_REQUESTED (Important). Findings: events/coverage aggregated across pairs and days; snapshots could omit session identity, cross pair/session windows, accept non-monotonic sequence, crossed/empty books.
- Re-review on `3020dfc30bca8432a4baa3455ed68c71f9a023a4`: CHANGES_REQUESTED (Important) for skipped increasing sequence IDs crossing a window. Fixed in `72c72ce09afe7a21c0d8c11872367c7d27f72783`; skipped IDs split context; non-increasing IDs reject.
- Final spec and quality verdict: PASS on exact code SHA `72c72ce09afe7a21c0d8c11872367c7d27f72783`; reviewer confirmed per-pair/day coverage, identity/boundary/gap/order validation and invalid-depth checks. Reviewer targeted suite: 9 passed.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PASS on exact code SHA `72c72ce09afe7a21c0d8c11872367c7d27f72783`; independent reviewer confirmed no remaining Critical/Important findings.
- Coordinator status: DONE after exact-SHA review PASS and planning validator PASS; this does not satisfy the separate external data/resource activation gates.

## Deviations and known risks
- Deviations: `BookSnapshot.session_id` is now required to guarantee the frozen dataset contract that samples never cross session boundaries.
- Unresolved issues / blockers: None for LOB-01. Real exchange LOB data ingestion requires production market maker feeds; synthetic/fixture validator satisfies research contract.
- Next unlocked consumers: L01-01, S04-01, S08-01.
