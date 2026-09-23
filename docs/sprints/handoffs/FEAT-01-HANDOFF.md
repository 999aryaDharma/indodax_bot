# FEAT-01 handoff

Status: DONE

## Identity
- Sprint ID: FEAT-01 — Versioned feature registry
- Implementation agent: Codex
- Independent reviewer: `/root/feat01_independent_review` (PASS on exact code SHA)
- Branch / worktree: `fix/feat-01-immutable-params` / `C:\Users\User\AppData\Local\Temp\indodax-pm04-v2-recovery`
- Base SHA: `ce322d7acaffef09cda2b2179b1fdbca943bfcda`
- Code SHA: `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab`
- Evidence SHA relation: recorded in this handoff

## Files and contracts
- Planned files:
- `configs/features/tabular_bar_v1.yaml` (newly created: exact 41 Wave 1 feature definitions)
- `src/indodax_lab/features/registry.py` (registry validators; params are now an immutable copied mapping and serialize as a dict)
- `tests/unit/lab/features/test_registry.py` (AC0..AC3 plus regression for immutable hashed params and serialization)
- Contract:
  - Registry YAML -> validated feature definitions and SHA-256 source hash.
  - Exactly 41 scalar Wave 1 features across 12 families (return, range, trend, momentum, trend_strength, volatility, bands, volume, liquidity, vwap, context, cross_section, regime, calendar, listing, quality).
  - Float64 features, no bfill allowed, strict lookback requirements enforced, content change without version bump rejected.
- Migration and compatibility:
  - Additive configuration and unit tests; backward compatible.
  - Dependencies: DATA-06 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| FEAT-01-AC0 (RED) | `test_feat_01_valid_contract` | `python -m pytest tests/unit/lab/features/test_registry.py` | Exit 1 (`FileNotFoundError: configs/features/tabular_bar_v1.yaml`) | `4bf3262` |
| FEAT-01-AC0 (GREEN) | `test_feat_01_valid_contract` | `python -m pytest tests/unit/lab/features/test_registry.py` | Exit 0 (8 passed in 0.84s) | working tree |
| FEAT-01-AC1 | `test_feat_01_contract_1` | `python -m pytest tests/unit/lab/features/test_registry.py::test_feat_01_contract_1` | Exit 0 (Passed, rejects duplicate & bfill) | working tree |
| FEAT-01-AC2 | `test_feat_01_contract_2` | `python -m pytest tests/unit/lab/features/test_registry.py::test_feat_01_contract_2` | Exit 0 (Passed, rejects lookback < formula requirement) | working tree |
| FEAT-01-AC3 | `test_feat_01_contract_3` | `python -m pytest tests/unit/lab/features/test_registry.py::test_feat_01_contract_3` | Exit 0 (Passed, rejects content change without version bump) | working tree |

The earlier uncommitted-working-tree results above are retained as provenance only. They are not used as current-SHA evidence.

Fresh verification on `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab`:
- Focused: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/features/test_registry.py tests/unit/lab/features/test_technical.py tests/unit/lab/features/test_availability.py -q -p no:cacheprovider` — 33 passed, exit 0.
- Full: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest -q -p no:cacheprovider` — 994 passed, 2 platform-limited skips, 3 warnings, exit 0.
- `ruff check src/indodax_lab/features/registry.py tests/unit/lab/features/test_registry.py` and `git diff --check` — exit 0.
- The mutable-param regression was observed RED before the fix; test execution is owner evidence. Windows symlink and Linux `/proc` skips remain explicit.

## Review
- Spec verdict: PASS (meets all functional requirements of FEAT-01 and dataset-feature-contracts §7.3).
- Quality verdict: Implementer verification PASS; params are immutable after hashing and registry serialization remains supported.
- Findings: Independent review of SHA `080401c` found Important mutable-param/hash-staleness issue; fixed in `0ed89f7`.
- Self-review: completed by implementation owner (Codex).
- Independent review: PASS on exact code SHA `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab`; independent AC0, immutability regression, and 5m registry checks passed (3 passed). Broader reviewer run hit Windows `tmp_path` ACL errors; owner verification on that SHA is 33 focused passes and 994 full-suite passes.
- Minor advisory: `model_copy(deep=True)` raises `TypeError` for the mapping proxy; reviewer found no repository callers. Revisit if deep-copying registry models becomes supported.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: none within FEAT-01 sprint scope. Minor advisory documented above.
- Next unlocked capabilities: FEAT-02 (Golden technical and liquidity transforms), FEAT-03 (As-of market context).
