# REPORT-01 handoff

Status: REVIEW

## Identity
- Sprint ID: REPORT-01 — Compact experiment reports
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/report-01-compact-experiment-reports`
- Base SHA: `9e1923f`
- Code target: `feat(report-01): compact experiment reports`
- Evidence SHA relation: `37a6b0fced4700f22b3032d51bf539d9fcde6a0e`

## Files and contracts
- Planned files:
  - `src/indodax_lab/reporting/summary.py` (ExperimentSummaryReport, generate_experiment_report_md, generate_experiment_report_json, generate_multi_run_comparison_md)
  - `src/indodax_lab/reporting/__init__.py` (Package exports)
  - `tests/unit/lab/reporting/test_summary.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `run artifacts -> Markdown/JSON summary with provenance, costs, baselines, validity and forward counts.`
  - Data quality, net performance, and rejection reasons are surfaced without reading raw logs.
  - No-data distinction: Missing, undefined, or zero-trade metrics are explicitly formatted as `NO_DATA` / `UNDEFINED` and never fabricated as `0.00%`.
  - Lineage isolation: Shared pipeline execution lineage (dataset snapshot ID, hashes, cost schedule, git SHA) is decoupled from candidate-independent strategy parameters.
  - Leaderboard integrity: Runs with status `INVALID_RUN` or outcome `INVALID_RUN` are excluded from ranking leaderboards and segregated into a dedicated Disqualified / Invalid Runs section.
- Migration and compatibility:
  - Additive reporting domain subsystem; compatible with EVAL-01, EVAL-02, EVAL-03, SIM-04.
  - Dependencies: EVAL-03 (DONE), SIM-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| REPORT-01-AC0 (RED) | `test_report_01_valid_contract` | `python -m pytest tests/unit/lab/reporting/test_summary.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.reporting') | `working tree` |
| REPORT-01-AC0 (GREEN) | `test_report_01_valid_contract` | `python -m pytest tests/unit/lab/reporting/test_summary.py::test_report_01_valid_contract` | Exit 0 (Passed, Markdown and JSON reports display data quality, net profit, and outcome clearly) | `37a6b0f` |
| REPORT-01-AC1 (RED) | `test_report_01_contract_1` | `python -m pytest tests/unit/lab/reporting/test_summary.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| REPORT-01-AC1 (GREEN) | `test_report_01_contract_1` | `python -m pytest tests/unit/lab/reporting/test_summary.py::test_report_01_contract_1` | Exit 0 (Passed, missing metrics render as NO_DATA, never 0.00%) | `37a6b0f` |
| REPORT-01-AC2 (RED) | `test_report_01_contract_2` | `python -m pytest tests/unit/lab/reporting/test_summary.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| REPORT-01-AC2 (GREEN) | `test_report_01_contract_2` | `python -m pytest tests/unit/lab/reporting/test_summary.py::test_report_01_contract_2` | Exit 0 (Passed, shared pipeline lineage separated from independent candidate parameters) | `37a6b0f` |
| REPORT-01-AC3 (RED) | `test_report_01_contract_3` | `python -m pytest tests/unit/lab/reporting/test_summary.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| REPORT-01-AC3 (GREEN) | `test_report_01_contract_3` | `python -m pytest tests/unit/lab/reporting/test_summary.py::test_report_01_contract_3` | Exit 0 (Passed, invalid runs excluded from leaderboard and placed in Disqualified section) | `37a6b0f` |

All 5 tests in `tests/unit/lab/reporting/test_summary.py` passed (1.21s).
Full lab suite verification: 134 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of REPORT-01 and docs/specs/18-reports-and-telegram.md).
- Quality verdict: PASS (clean markdown/json output, strict no-data semantics, robust lineage isolation, leaderboard disqualification).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for REPORT-01.
- Next unlocked consumers: REPORT-02, AGENT-01.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ## Sprint-review fix cycle (CHANGES_REQUESTED)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 1 - CRITICAL - a run with no net profit measurement was still given a leaderboard rank

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `_rank_key` substituted `float("-inf")` for a missing `net_profit_pct` and then sorted every entry with `reverse=True`. A run that produced no performance data was therefore still assigned a leaderboard position, displayed alongside real measurements as though it had been compared. The report then asserted a ranked outcome that was never measured, which is the exact failure the sprint exists to prevent: the spec's acceptance boundary "No-data berbeda dari zero profit" and the rule "missing data is unavailable not zero". `float("-inf")` is a *sort* sentinel, not a value, and treating it as a rankable number is what turns "no data" into a reported result. The pre-existing AC1 test only asserted the single-run Markdown path and never exercised the leaderboard, so this was unobserved.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/reporting/test_summary.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/reporting/test_summary.py:247: AssertionError: assert '| 2 | cand_unmeasured' not in '## Experime...ess | PASS |'` (test_leaderboard_does_not_rank_a_run_with_no_net_profit_data). The rendered leaderboard contained the literal row `| 2 | cand_unmeasured | run_unmeasured | NO_DATA | NO_DATA | 0 | success | PASS |`, i.e. a measured run ranked above an unmeasured one and both were presented as ranked.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: ranking is now gated on a real measurement. A new `_finite_metric` helper returns a value only for a finite int/float and returns `None` for a missing key, `None`, a bool, a non-numeric value, NaN and +/-infinity, because all of those mean "no usable measurement" rather than a number. `generate_multi_run_comparison_md` partitions valid entries into ranked and unranked; a run without a finite `net_profit_pct` receives no rank and is rendered in a new `### Unranked / No Data` section with the reason stated, so nothing is hidden and no position is fabricated. `_format_metric_display` also returns `NO_DATA` for bools and non-finite floats so a NaN or infinity can never be printed as a numeric percentage such as `inf%`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/reporting -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `25 passed in 1.36s`, from `5 failed, 5 passed` at RED across this cycle. `test_leaderboard_does_not_rank_a_run_with_a_non_finite_net_profit` covers the NaN and infinity variants of the same defect.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/reporting/summary.py`, `tests/unit/lab/reporting/test_summary.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 2 - CRITICAL - unescaped values let a persisted run record forge a leaderboard row

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): every untrusted value in both report renderers - run id, candidate id, status, outcome, lineage values, parameter names and values, gate names and rejection reasons, and every metric key - was interpolated raw into a Markdown table row. A value containing a newline therefore started a new physical line, and a value containing pipes started new columns. Candidate ids and rejection reasons originate from persisted `ExperimentRunRecord` rows written by a backtest or strategy run, so a crafted or corrupted record could inject a row that renders identically to a real ranked candidate. The result is fabricated performance evidence in the report a user reads to decide promotion, which is a report-integrity failure and not a cosmetic one. The spec requires "escape Markdown" for this subsystem; the sibling REPORT-01 rendering path had no escaping at all, only the Telegram surface did.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/reporting/test_summary.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/reporting/test_summary.py:352: AssertionError: assert not True` where `True = any(generator)` (test_report_escapes_markdown_structure_in_untrusted_values). The payload `cand_hostile\n| 99 | cand_forged | run_forged | 999.00% | 99.00 | 99 | success | PASS |` produced a standalone `cand_forged` leaderboard row, indistinguishable from a real ranked run.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: a single `_md_cell` helper now renders every dynamic value before interpolation in both `ExperimentSummaryReport.to_markdown` and `generate_multi_run_comparison_md`. It replaces the table-structure characters - pipe, carriage return, newline, tab and the remaining ASCII control range - with a single space, so no value can terminate its own cell or open a new row or column. Full MarkdownV2 special-character escaping is deliberately not applied here, because these artifacts are consumed as Markdown by humans and REPORT-02 already owns full escaping for the Telegram surface; the defect being fixed is table-structure forgery, not Telegram parse compatibility.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Contract change flagged for the coordinator: a metric value or candidate id containing a pipe or newline now renders with those characters replaced by spaces rather than verbatim. That is intended, but a downstream consumer that string-matched a report cell containing a literal pipe would see the sanitized form. No consumer in `src/` or `tests/` parses these report strings, so the affected-subsystem gate is the proof.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: covered by the `25 passed in 1.36s` run above.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/reporting/summary.py`, `tests/unit/lab/reporting/test_summary.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 3 - IMPORTANT - the run's own failure reason was absent from the human-readable report

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important): `ExperimentSummaryReport` carries `error_message` and `from_run` populates it, and it reaches the JSON artifact, but `to_markdown` never rendered it. For a crashed or failed run the Markdown report showed only the evaluator's generic gate rejection reasons, so the actual cause - for example a dataset snapshot that could not be read - existed only in the JSON and the raw logs. That is a direct failure of the sprint's headline acceptance criterion, "Pengguna dapat melihat kualitas data, performa net dan alasan penolakan tanpa membaca raw logs": the user had to read the raw logs to learn why the run failed. It is also an asymmetry inside one module, since the multi-run leaderboard already reached for `run.error_message` as a fallback and the single-run report did not.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/reporting/test_summary.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/reporting/test_summary.py:313: AssertionError: the run's actual failure reason must be in the report` / `assert 'DATA_LOAD_FAILED' in '## Experiment Summary: run_crashed\n\n### Candidate Information\n- **Candidate ID**: ...'` (test_summary_markdown_reports_the_run_error_message).
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: `to_markdown` now emits a `### Run Error` section with the sanitized `error_message` when one is set, and emits nothing when the run has no error, so a clean run is not given an empty failure section.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: covered by the `25 passed in 1.36s` run above. The negative case (a clean run must not render the section) is asserted in the same test.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/reporting/summary.py`, `tests/unit/lab/reporting/test_summary.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 4 - IMPORTANT - leaderboard ordering was not reproducible from the same input set

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important): the old sort key was `(net_profit_pct, sharpe_ratio)` with `reverse=True`, which is not a total order. Any two runs with identical metrics compared equal and fell back to input order, so the rendered leaderboard depended on the order the caller happened to pass the runs in. A report that cannot be re-derived from the same artifacts later is not reproducible evidence, and the spec requires an "Idempotent report key and bounded delivery retries" for this subsystem. Separately, a NaN key made the ordering arbitrary in a way that depended on CPython's sort internals rather than on the data, which is the same class of defect as Finding 1 and is fixed by the same `_finite_metric` gate.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/reporting/test_summary.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/reporting/test_summary.py:376: AssertionError: identical input set must produce an identical leaderboard` - the same three tied runs rendered `cand_tie_2` first in one call and `cand_tie_0` first in the other purely because the input list was reversed (test_leaderboard_preserves_each_run_identity_end_to_end).
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the sort key is now a total order, `(-net_profit_pct, -sharpe_ratio, run_id)`, so profit and Sharpe rank descending with a stable, deterministic run-id tiebreak. The unranked section is sorted by `run_id` for the same reason. Reordering the input now produces a byte-identical leaderboard.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: covered by the `25 passed in 1.36s` run above.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/reporting/summary.py`, `tests/unit/lab/reporting/test_summary.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Affected-subsystem gate

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Command: `python -m pytest tests/unit/lab/orchestration tests/unit/lab/reporting tests/unit/lab/verification tests/integration/lab/test_telegram_status.py tests/regression/test_release_candidate.py tests/research/test_rl_reward_contract.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Result: `109 passed in 3.44s`, up from the 104-test post-JOB-02 baseline by exactly the 5 tests added in this cycle, with no regression. A repository-wide grep confirms `generate_multi_run_comparison_md`, `generate_experiment_report_md` and `ExperimentSummaryReport` have no callers in `src/` outside `indodax_lab/reporting`, so the new section layout and the sanitized cell rendering have no other production consumer in this repository.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Capability gaps and deferred items

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Capability gap per AGENTS.md: `ruff` is not installed, so no lint gate was run. `pyarrow` is not installed, so `tests/unit/lab/models/lob/` fails collection and was excluded.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Deferred (Minor) - not blocking: `_md_cell` neutralizes table-structure characters only, not the full MarkdownV2 set that REPORT-02 escapes. That is intentional for the Markdown artifact, but a caller that pipes `generate_experiment_report_md` output straight into a Telegram send without REPORT-02's escaping would still be exposed. Recorded as backlog; the correct fix is to route through `escape_telegram_markdown`, which is REPORT-02's owned surface.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Deferred (Minor) - not blocking: `_md_cell` replaces offending characters with a space rather than escaping them, so two distinct values differing only in a pipe could render identically. Pre-existing ambiguity in a human-readable report; recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Deferred (Minor) - not blocking: the `### Unranked / No Data` section does not distinguish *why* a run was unrankable (missing key, `None`, NaN, infinity, non-numeric). It states that the run is unranked, which satisfies the no-data boundary, but a richer reason column would help triage. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Deferred (Minor) - not blocking: `to_markdown` still renders `data_quality_score` as a percentage plus a raw fraction with no validity floor, so a run with a known-bad data quality reads as a normal 0.0% figure. The value is reported faithfully; whether the report should visibly mark a below-threshold quality score is a product decision, recorded as backlog.

## Independent review remediation — evaluation provenance and stable invalid output

- Review target: `9b6dab1239ae89eb8edbe22c4ec194f802173cd4`. The reviewer reproduced swapped run/evaluation pairs that showed a mismatched candidate as PASS, and showed the invalid-run section changed bytes when input order was reversed.
- Remediation SHA: `5c587dec44afa33d68381bdfb3d82a9ce768cfcf` (`fix(report-01): bind evaluations to run identity`).
- `_validate_evaluation_identity` now requires matching `run_id` and `candidate_id` before either single-run summary creation or leaderboard classification; mismatches raise `EVALUATION_IDENTITY_MISMATCH` naming the mismatched fields.
- Disqualified rows sort by `(run_id, candidate_id)`, making output independent of caller order.
- New regressions: single-summary mismatch, swapped leaderboard evaluations and reversed invalid-run input order. RED: 3 failed; GREEN: `tests/unit/lab/reporting/test_summary.py` -> **13 passed**.
- Affected gate: `tests/unit/lab/orchestration tests/unit/lab/reporting tests/unit/lab/verification tests/integration/lab/test_telegram_status.py tests/regression/test_release_candidate.py tests/research/test_rl_reward_contract.py` -> **144 passed**.
- `git diff --check` passed. Ruff reports existing findings in `summary.py`; no clean lint claim is made.
- Final independent review: **PASS** at exact remediation SHA `5c587dec44afa33d68381bdfb3d82a9ce768cfcf`; reviewer ran 13 focused tests and identity probes. Owner's 144-test broader gate was not independently rerun.

## Independent reviewer identity — closes the held transition (2026-09-27)

- The remediation section above recorded a PASS but no reviewer session, so the
  manifest held REPORT-01 at REVIEW (DONE requires an identified independent
  approver; identity is never fabricated).
- Fresh read-only independent review: opencode session
  `ses_f1d0bbf80ffe96pu8qNkXrwGag` at HEAD `0735ff55b9820648c7d767caa8a3db5478275f58`
  (remediation SHA `5c587dec44afa33d68381bdfb3d82a9ce768cfcf` confirmed ancestor,
  exit 0). Verdict: **PASS**, no Critical/Important findings.
- Fresh evidence: `tests/unit/lab/reporting/` 34 passed exit 0 (test_summary.py
  13 passed); orchestration+verification 86 passed; full affected gate incl.
  telegram status, release candidate, RL reward = 156 passed exit 0. In-memory
  probe: byte-identical output under reversed input; EVALUATION_IDENTITY_MISMATCH
  raises in both entry points; unmeasured run rendered NO_DATA/unranked; module
  performs no I/O.
- Minor backlog unchanged (MarkdownV2 escaping owned by REPORT-02, `_md_cell`
  space substitution, unranked reason granularity, data-quality threshold).
- Sprint remains REVIEW until coordinator updates the shared manifest and projections after the concurrent manifest edits are resolved.
