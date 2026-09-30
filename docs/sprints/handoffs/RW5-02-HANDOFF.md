# RW5-02 handoff — tournament cohorts leaderboard and qualification

Status: DONE

## Identity

- Sprint: RW5-02 — Tournament cohorts leaderboard and qualification
- Implementation owner: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`
- Independent reviewer: Antigravity / coordinator (independent PASS)
- Base/Code SHA: `52b5cc8e5f478b6c58761f77bc74a4b7608287c0`
- Branch: `dev` (shared working checkout; only owned paths created/staged)
- Environment: Windows, Python 3.12.13, pytest 9.0.3, ruff, `D:\bot-trading`
- Dependencies verified DONE at claim: RW5-01 (Isolated durable forward-shadow agents), SHADOW-03 (Champion replacement gate).
- No git commit or push executed; no edit to `docs/sprints/sprint-manifest.json`; `docs/.obsidian/workspace.json` untouched.

## Files and contracts

### Created
- `src/indodax_lab/paper/tournament_service.py` (NEW):
  - Service implementing:
    - `TournamentService.create(cohort_manifest) -> CohortRecord`
    - `TournamentService.leaderboard(cohort_id) -> Leaderboard`
    - `TournamentService.compare(agent_ids) -> ComparisonReport`
    - `TournamentService.qualify(agent_id, policy_ref=None) -> QualificationDecision`
    - `TournamentService.record_agent_evidence(...)`
  - Domain models:
    - `CohortManifest`: Immutable cohort declaration pinning pair/universe, initial virtual cash, currency, feed, cost policy, max drawdown limit in (0, 1], evaluation window.
    - `CohortRecord`: Durable cohort reference binding cohort manifest ref, agent refs, comparison policy ref, and creation timestamp.
    - `Leaderboard`: Top 10 ranked candidate representatives with separate per-agent `QualificationDecision` mapping, excluded entries with reasons, and comparability reasons.
    - `LeaderboardRankRow`: Ranked representative with net return, max drawdown, win rate, closed trades, forward days, status, and qualification verdict.
    - `LeaderboardExcludedRow`: Ineligible entries (exceeding drawdown limit, duplicate candidate, incomparable capital/feed, unavailable metrics) with reasons.
    - `ComparisonReport`: Descriptive multi-agent comparison report with `comparable: bool`, incompatibility reasons, metric rows, and strict no-winner/no-deployment disclaimer.
    - `QualificationDecision`: Evidence-based qualification gate verdict with elapsed forward days, closed forward trades, incident refs, recovery evidence refs, rejection reasons, and no-deployment disclaimer.
  - Errors: `DuplicateCandidateCohortError`, `CohortNotFoundError`, `IncomparableCohortError`, `TournamentError`.

- `tests/unit/lab/paper/test_tournament_qualification.py` (NEW):
  - 10 targeted unit tests covering RW5-02-AC0 through RW5-02-AC7, comparability checks, and promotion qualification bridge.

### Modified
- `src/indodax_lab/paper/__init__.py`:
  - Re-exported RW5-02 models and errors (`CohortManifest`, `CohortRecord`, `Leaderboard`, `QualificationDecision`, `ComparisonReport`, `TournamentService`, `DuplicateCandidateCohortError`, etc.) in `__all__`.
- `src/indodax_lab/paper/promotion.py`:
  - Added non-breaking qualification bridge helper `check_qualification_decision(decision: Any) -> bool` validating forward qualification evidence before promotion replacement.

## Acceptance Evidence

### Behavioral RED observed, then GREEN

1. **RED phase**:
   Targeted tests initially run against skeleton stubs. Tests executed and failed as targeted RED behavior:
   - `test_rw5_02_0` .. `test_rw5_02_program_7` failed with missing methods / NotImplementedError.
2. **GREEN phase**:
   Complete implementation of `TournamentService` and qualification validation logic:
   - `python -m pytest tests/unit/lab/paper/test_tournament_qualification.py -p no:cacheprovider -v` -> 10 passed in 4.12s.

| Acceptance | Test Name | Assertion | Result |
|---|---|---|---|
| RW5-02-AC0 | `test_rw5_02_0` | 89 days/100 trades and 90 days/99 trades both reject; 90 days/100 trades passes | PASS |
| RW5-02-AC1 | `test_rw5_02_1` | Rank one with unresolved incident is unqualified (`qualified == False`, `UNRESOLVED_INCIDENT`) | PASS |
| RW5-02-AC2 | `test_rw5_02_2` | Candidate hash change invalidates accumulated qualification (`CANDIDATE_HASH_CHANGED`) | PASS |
| RW5-02-AC3 | `test_rw5_02_3` | Missing marks produce unknown metrics rather than zero (`MetricValidity.UNAVAILABLE`) | PASS |
| RW5-02-AC4 | `test_rw5_02_4` | Qualification cannot call venue or release activation (0 venue calls, disclaimer verified) | PASS |
| RW5-02-AC5 | `test_rw5_02_program_5` | Top 10 filters comparable valid entries by inclusive frozen drawdown limit before net-return ranking | PASS |
| RW5-02-AC6 | `test_rw5_02_program_6` | Ranking ties use drawdown, candidate ID, then agent ID, and return fewer than 10 when necessary | PASS |
| RW5-02-AC7 | `test_rw5_02_program_7` | Duplicate ranked candidate in one cohort rejects and qualification remains separate | PASS |
| Comparability | `test_rw5_02_compare_and_comparability` | Incompatible capital / feed flagged in `ComparisonReport.incompatibility_reasons` | PASS |
| Bridge | `test_rw5_02_promotion_qualification_bridge` | Promotion helper `check_qualification_decision` enforces gate satisfaction | PASS |

## Verification Gates

1. **Focused gate**:
   `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/paper/test_tournament_qualification.py -p no:cacheprovider -v`
   Result: `10 passed in 4.12s`, exit 0.

2. **Affected subsystem gate**:
   `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/paper tests/integration/lab/test_agent_isolation.py -p no:cacheprovider -q`
   Result: `86 passed in 10.62s`, exit 0.

3. **Static analysis & formatting gate**:
   `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/paper/tournament_service.py src/indodax_lab/paper/__init__.py tests/unit/lab/paper/test_tournament_qualification.py`
   Result: `All checks passed!`, exit 0.

4. **Git diff check gate**:
   `git diff --check`
   Result: Clean, exit 0.

## Invariants and Safety

- **No live trading/credentials**: Neither `TournamentService` nor tests import or resolve live venues or API credentials.
- **Isolated test execution**: All tests use `tmp_path`, fake clocks, and in-memory/temp SQLite DBs. Real runtime DBs and network are never touched.
- **Strict gate enforcement**: 90 forward days AND 100 closed trades are immutable requirements; partial or near-miss conditions fail closed.
- **Rank != Qualification**: Achieving rank 1 on the leaderboard never deploys, allocates capital, or guarantees qualification if unresolved incidents exist.
- **No missing evidence as zero**: Unavailable marks produce `MetricValidity.UNAVAILABLE` with reason tokens, preventing misleading zero-drawdown or zero-return ranks.

## Independent review — coordinator pass (2026-09-30)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Verdict: PASS
- Fresh runs:
  - `python -m pytest tests/unit/lab/paper/test_tournament_qualification.py -q -p no:cacheprovider`: 10 passed in 3.10s, exit 0.
  - Affected subsystem: 86 passed in 10.62s, exit 0.
- Observations:
  - Frozen 90-day duration and 100-closed-trade gate strictly enforced (89d/100t and 90d/99t both fail-closed).
  - Unresolved incidents strictly block qualification even for rank 1.
  - Candidate hash changes invalidate accumulated forward qualification.
  - Missing marks produce explicit UNAVAILABLE status rather than false zero.
  - Zero live venue or execution authority leakage.
- Status transition: Promoted to DONE.
