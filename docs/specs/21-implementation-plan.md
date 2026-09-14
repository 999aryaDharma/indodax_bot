# Feature-driven roadmap

This is ordering and scope, not a calendar or implementation script. Sprint = independently reviewable capability. Detailed instructions belong to each feature sprint.

| Gate | Required capabilities | Evidence and next unlock |
|---|---|---|
| A — baseline trust | BASE-01…06 | Historical Phase 0 evidence; protects compatibility |
| B — reproducible data | DATA-01…06, UNIV-01, BAR-01 | Historical Phase 1 offline evidence; FEAT-01 and COST-01 currently READY |
| C — trustworthy judge and training inputs | FEAT-01…04, COST-01, LED-01, SIM-01…04, LABEL-01…02, SPLIT-01, TRAIN-01 | Exact replay + leakage tests before comparisons |
| D — Wave 1 tournament | Registered eight classical/small-cap + M01/M02, evaluation and bounded jobs | QA-01 proves joined offline workflow; no profitability inference |
| E — forward paper operation | SHADOW-01…02 + operations/reporting | Actual continuous forward evidence starts only when frozen candidate records decisions |
| F — research software release | QA-02, QA-03, REL-01 | Security/recovery/resources demonstrated; champion gate can remain pending |
| G — qualified champion | SHADOW-03 | >=90 days AND >=100 closed forward trades with policy compliance |
| Optional research | catalog extension, DL/graph/foundation/LOB/RL | Activated selectively after prerequisites and external evidence; not required for initial paper software release |

## Starting from the existing repo

Tasks 1–14 have committed historical completion. Task 15 has untracked partial implementation in the original branch. Start FEAT-01 by auditing that WIP, taking only scoped useful changes, proving tests and handing off for independent review; do not copy all WIP into one commit. COST-01 can run independently once official schedule evidence is collected. Its historical unknown periods remain blocked for promotion rather than filled from current rates.

## Dependency correction from the old task list

Old Task 16 (labels) consumes execution/cost interfaces in Tasks 17–18. Chronological task numbering was not a correct dependency DAG. New LABEL-01 waits for SIM-01 and FEAT-04. Strategy protocol depends on a testable judge; model training waits for separated features/labels/folds. This prevents implementing labels with a second inconsistent fee calculation.

## Parallelism and rollout

See execution waves for exact dependency depth. Resource, file ownership and worktree restrictions still apply. No reimplementation of historical DONE tasks by default; defects use a change request that reopens the affected capability and invalidates dependent READY states until review is complete.

No payment, paid data subscription, service activation, live strategy execution or merge to default branch is implied by this roadmap. Those require their corresponding explicit operational action and evidence.
