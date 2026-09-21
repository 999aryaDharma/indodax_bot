# RP-01 Handoff — Shared SignalIntent ownership with compatibility

Status: REVIEW

## Identity

- Task: RP-01
- Implementation owner: Codex `/root` (LUNA execution)
- Independent reviewer: `/root/architecture_doc_review`
- Base SHA: `5924a70`
- Code SHA: `7385194`
- Branch: `docs/architecture-runtime-plan`
- Scope: shared decision contract ownership and import compatibility only

## Implemented

- Added the single `SignalIntent` class definition at `src/indodax_lab/contracts/decision.py`.
- Kept `src/indodax_lab/backtest/events.py` as a legacy compatibility re-export of the same class object.
- Updated canonical source consumers across backtest, strategy, portfolio, risk, control, model, CLI, and shadow modules to import the shared contract directly.
- Added AST ownership and compatibility characterization tests.
- Preserved fields, validators, defaults, enum wire values, Decimal serialization, and UTC rejection behavior.

## Observed TDD evidence

- RED: `python -m pytest tests/architecture/test_decision_contract_ownership.py -q -k has_one_shared_owner -s` failed with the expected old owner `src/indodax_lab/backtest/events.py`.
- Characterization before move: 19 tests passed in `tests/unit/lab/test_decision_contract_compatibility.py`.
- GREEN focused: `python -m pytest tests/architecture/test_decision_contract_ownership.py tests/unit/lab/test_decision_contract_compatibility.py -q` → 21 passed.
- Fresh-process identity check → `True` for shared and legacy imports.
- `python -m compileall` for changed source paths → exit 0.
- `git diff --check` → exit 0.

## Full-suite gate

`python -m pytest -q` was attempted at code SHA `7385194` and could not collect the repository suite because this environment lacks required declared research dependencies, including `pandas`, `pyarrow`, and `scipy`. No dependency was installed into the shared environment. This is an external environment blocker, not a test pass claim.

The required focused suite is green. Existing repository lint also reports pre-existing violations in touched strategy files; the moved contract itself has no new reported violation after removing obsolete event imports. Full lint remains blocked by the baseline findings and unavailable research environment.

## Compatibility and migration

No schema, field, default, validator, persistence, venue, accounting, or execution behavior changed. Existing `indodax_lab.backtest.events.SignalIntent` imports remain valid and resolve to the shared class. New code should import `indodax_lab.contracts.decision.SignalIntent` directly.

## Safety and scope checks

- No credentials, real order authority, network calls, runtime databases, or production activation were used.
- No `main` change, merge, push, or deployment.
- No product-path files outside the declared RP-01 source/test scope were modified.

## Reviewer decision

Pending independent review. Coordinator must not mark the manifest DONE until the reviewer records PASS on this exact code SHA and the external full-suite gate is resolved or explicitly preserved as a blocker.
