# AUD-008 temporal defect correction

Date: 2026-09-15. User authorization: continue audit fixes directly on `dev`.
Scope: LABEL-01 / SPLIT-01 / TRAIN-01; restore accepted ADR-002, not a new capability.

## Impact and compatibility

The existing schema drops label availability before training. Add optional
`label_available_at` to SampleRecord and optional fold start/end evidence to
FoldAssignment. Old records remain readable; unknown availability is EXCLUDED
rather than inferred from event time. Training refuses active assignments with
missing fold boundaries. Consumers: assign_folds, materialize_training_dataset,
and the existing build_training_dataset CLI. No database migration, service,
dependency change, or rewriting of stored artifacts is authorized.

Use half-open fold windows and purge labels available at or beyond the fold end.
Persist availability in training output and verify the join's pair/decision
identity. This is a conservative cutoff at fold end, not authorization to fit
at an earlier time. Future trainers must still enforce their actual fit cutoff.

Existing synthetic tests must declare their actual availability and fold bounds;
never add fallback values to production. Rebuild affected artifacts from verified
sources under new IDs; never mutate old artifacts or reseal exposed data.
Rollback disables consumption of new output; old unsafe training is not promoted.

## Execution checklist

- [x] Reproduce delayed entry observation and cross-pair label contamination.
- [x] Preserve maximum outcome availability and reject incomplete/unclosed sources.
- [x] Reproduce delayed label acceptance and shared fold boundary errors.
- [x] Carry explicit cutoff evidence through fold assignment and reject unknowns.
- [x] Reproduce dropped availability and mismatched temporal joins in training.
- [x] Enforce cutoff and preserve availability in materialized output.
- [x] Focused and regression tests, full-suite attempt, independent working-diff review.

Manifest remains unchanged; no sprint DONE or complete audit PASS is implied.

Evidence: [temporal fix handoff](../sprints/handoffs/AUD-temporal-fix-20260915.md).
