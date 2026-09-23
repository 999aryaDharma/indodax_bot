# FEAT-01 independent review

Status: CHANGES REQUESTED on `080401c78a73f54ed9447e967ce80393220ca643`; exact follow-up SHA `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab` awaits review.

## Round 1 — 2026-09-23

- Important: `FeatureDefinition.params` was a mutable dict despite `frozen=True`. Mutating it changed a loaded feature while `LoadedFeatureRegistry.source_id` retained its previous exact-source hash. Fix requires an immutable defensive copy and a regression test.
- Reviewer exact-SHA evidence on `080401c`: AC0 test passed (1 passed). Focused test file was not fully verified because Windows denied pytest `tmp_path` access (2 passed, 6 setup errors).

## Follow-up implementation

- Owner fix: `MappingProxyType(dict(value))` makes each validated params mapping immutable and detached; a Pydantic field serializer restores normal dict serialization for manifest consumers.
- Regression test rejects mutation, verifies original value/hash are stable, and exercises JSON-mode serialization.
- Current code target: `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab`.
- Independent re-review and final verdict: PENDING.
