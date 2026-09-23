# FEAT-01 independent review

Status: PASS on exact follow-up SHA `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab` (2026-09-23).

## Round 1 — 2026-09-23

- Important: `FeatureDefinition.params` was a mutable dict despite `frozen=True`. Mutating it changed a loaded feature while `LoadedFeatureRegistry.source_id` retained its previous exact-source hash. Fix requires an immutable defensive copy and a regression test.
- Reviewer exact-SHA evidence on `080401c`: AC0 test passed (1 passed). Focused test file was not fully verified because Windows denied pytest `tmp_path` access (2 passed, 6 setup errors).

## Round 2 — 2026-09-23 — `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab`

- Verdict: PASS. No Critical or Important findings remain.
- Independent checks: AC0, immutable-params regression, and 5m registry test — 3 passed. The broader reviewer run remained limited by Windows `tmp_path` permission errors; owner ran 33 focused tests and the full suite on the same code SHA.
- Minor advisory: `model_copy(deep=True)` raises `TypeError` because `mappingproxy` is not pickleable. Reviewer found no repository callers; revisit if deep-copying registry models becomes supported.

## Follow-up implementation

- Owner fix: `MappingProxyType(dict(value))` makes each validated params mapping immutable and detached; a Pydantic field serializer restores normal dict serialization for manifest consumers.
- Regression test rejects mutation, verifies original value/hash are stable, and exercises JSON-mode serialization.
- Current code target: `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab`.
- Independent re-review: PASS on exact code SHA `0ed89f745f8153d7f11dc4cb8edec30bbb8063ab`; see Round 2.
