# Temporal audit fixes — dev — 2026-09-15

Status: scoped working-tree review PASS (round 3); committed-SHA final review pending.
Base HEAD: `0c788c0d432eb67440c9fdfb41b2e9f21ada4f41`.
No commit, push, service activation, real credentials, runtime database mutation,
dependency installation or sprint-status change.

## Scope and behavior

AUD-008 corrections implement the existing ADR-002 cutoff invariant across:

- `src/indodax_lab/labels/returns.py`: only requested pair supplies prices;
  maximum availability across outcome bars; UTC source timestamps; no duplicate,
  unclosed, gapped outcome or closed-bar availability preceding close.
  The frame adapter retains `exit_ts` and adds canonical `label_end_ts` derived
  from that event, allowing actual output to enter split/training interfaces.
- `src/indodax_lab/labels/splits.py`: explicit label availability; missing values
  become EXCLUDED rather than inferred; half-open decision, purge, embargo and
  exposure boundaries; active assignments carry their fold start/end.
- `src/indodax_lab/labels/materializer.py`: mandatory non-null UTC evidence;
  equal sample sets and matching pair/decision identities; no silently dropped
  label availability; active data must satisfy declared fold cutoff.

Tests changed in `tests/unit/lab/labels/test_returns.py`, `test_splits.py`, and
`tests/integration/lab/test_training_materialization.py`. Synthetic old fixtures
now declare actual availability and non-overlapping fold windows; production
does not fill missing evidence. Integration uses actual `assign_folds` output
and verifies a delayed label is PURGED and absent from TRAIN.

## Verification evidence

Interpreter: `C:/Users/User/miniconda3/envs/ML/python.exe` (Python 3.12.13).
All pytest commands use `-B -q -p no:cacheprovider --tb=short`.

| Command / scope | Exit | Result |
| --- | --- | --- |
| `-m pytest tests/unit/lab/labels/test_returns.py` initial RED | 1 | 5 failed, 4 passed |
| `-m pytest tests/unit/lab/labels/test_splits.py` initial RED | 1 | 3 failed, 4 passed |
| `-m pytest tests/integration/lab/test_training_materialization.py` initial RED | 1 | 8 failed, 4 passed |
| Return + split negative additions before fixes | 1 | 4 failed, 15 passed |
| Adjacent exposure reviewer reproductions before fix | 1 | 2 failed, 7 passed |
| Early closed-bar availability before fix | 1 | 1 failed, 12 passed |
| Real label-frame integration + partial/early bar before fixes | 1 | 2 failed, 13 passed |
| `-m pytest tests/unit/lab/labels tests/integration/lab/test_training_materialization.py` latest focused | 0 | 42 passed |
| Network-blocked regression before final two reviewer fixes | 0 | 91 passed, no skips |
| Network-blocked regression after all reviewer fixes | 0 | 93 passed, no skips |
| Full suite via `pytest.main(['-q', ...])` | 2 (pytest) | Collection blocked: 2 missing `pandas_ta` import errors; shell wrapper reports exit 1 |
| `-m ruff check src/indodax_lab/labels tests/unit/lab/labels tests/integration/lab/test_training_materialization.py` | 1 | `No module named ruff`; not lint PASS |
| In-memory `compile()` of six changed Python files | 0 | `COMPILE_OK: 6 files` |
| `git diff --check` | 0 | CRLF conversion warnings only |
| `-B docs/quality/validate_planning.py` | 1 | Existing sprint-manifest JSON corruption at line 1; not changed |

Regression paths:

```text
tests/unit/lab/labels
tests/unit/lab/backtest
tests/unit/lab/paper
tests/integration/lab/test_training_materialization.py
tests/integration/lab/test_backtest_golden.py
```

Regression ran through `pytest.main` with the above flags, plus
`-o tmp_path_retention_policy=all --basetemp <new unique system-temp path>`.
Socket connect/connect_ex/create_connection were blocked and test-only fake
credentials explicitly replaced environment values. Elevated temp access was
needed for Windows pytest fixtures. Existing temporary artifacts were not removed.

## Review

Independent reviewer `/root/label_temporal_fix_review` found an Important boundary
case: adjacent exposure incorrectly blocked a sealed fold. Two negative cases
reproduced the problem; half-open overlap corrected it, while the prior genuine
overlap rejection test continues to pass. Round 2 found the missing label-frame
boundary alias and early partial-bar classification. Both were reproduced before
fixing; the new test passes an actual generated return-label frame through the
split and training functions. Round 3 independently returned scoped PASS with no
unresolved Critical/Important findings. Reviewer reported 37 passing subset tests
and a clean scoped diff check; parent final regression independently passed 93.
No committed-SHA final approval or DONE status is claimed.

## Compatibility and remaining blockers

See [impact note](../../quality/AUD-008-temporal-correction.md). Additive optional
fields allow old records to be read, not trusted for training. Missing active fold
boundaries now fail closed. Never overwrite historical output or reseal exposed
data; rebuild from verified source evidence before reuse.

This patch is not complete release qualification. The actual trainer must still
enforce an earlier fit time if it differs from declared fold cutoff. AUD-009
training identity/checksum completeness and deterministic split identity remain
open: do not reuse cached datasets as evidence based on current IDs. Full
execution-model alignment, feature/DL leakage, artifact/recovery safety, model
claims and governance findings remain open. No profitability inference is made.

`requirements.txt` remains unchanged from the user's original working copy,
SHA-256 `01e97526e4b9fd5ef2110aa308609ea70dad0d6084335ea55ad27d53b9f9630c`.

Overall branch verdict remains **BLOCKED**.
