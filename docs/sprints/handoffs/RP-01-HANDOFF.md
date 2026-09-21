# RP-01 Handoff — Shared SignalIntent ownership with compatibility

Status: DONE — code review PASS; full-suite gate PASS in declared research environment

## Identity

- Task: RP-01
- Implementation owner: Codex `/root` (LUNA execution)
- Independent reviewer: `/root/architecture_doc_review`
- Base SHA: `5924a70`
- Code SHA: `5d9629e`
- Branch: `docs/architecture-runtime-plan`
- Scope: shared decision contract ownership and import compatibility only

## Implemented

- Added the single `SignalIntent` class definition at `src/indodax_lab/contracts/decision.py`.
- Kept `src/indodax_lab/backtest/events.py` as a legacy compatibility re-export of the same class object.
- Updated canonical source consumers across backtest, strategy, portfolio, risk, control, model, CLI, and shadow modules to import the shared contract directly.
- Added AST ownership and compatibility characterization tests.
- Made the historical `indodax_lab.backtest` flat exports lazy so shared-first contract imports do not enter the execution graph during package initialization.
- Added fresh-process checks for both shared-first and legacy-first import order.
- Preserved fields, validators, defaults, enum wire values, Decimal serialization, and UTC rejection behavior.

## Observed TDD evidence

- RED: `python -m pytest tests/architecture/test_decision_contract_ownership.py -q -k has_one_shared_owner -s` failed with the expected old owner `src/indodax_lab/backtest/events.py`.
- Characterization before move: 19 tests passed in `tests/unit/lab/test_decision_contract_compatibility.py`.
- GREEN focused: `python -m pytest tests/architecture/test_decision_contract_ownership.py tests/unit/lab/test_decision_contract_compatibility.py -q` → 21 passed.
- Fix RED: shared-first fresh-process import reproduced a circular `backtest.__init__` → `engine` → `events` cycle.
- Fix GREEN: the same focused command → 23 passed; both fresh-process import checks pass.
- Fresh-process identity check → `True` for shared and legacy imports.
- `python -m compileall` for changed source paths → exit 0.
- Targeted Ruff for the new package initializer, architecture test, and risk engine → all checks passed.
- `git diff --check` → exit 0.

## Full-suite gate

Full suite gate is RESOLVED. Rerun in the pre-existing isolated research environment (`C:\Users\User\miniconda3\envs\ML\python.exe`, Python 3.12.13 with pandas 2.2.3, pyarrow 24.0.0, scipy 1.18.1):

- `python -m pytest tests/architecture/test_decision_contract_ownership.py tests/unit/lab/test_decision_contract_compatibility.py -q` → 23 passed in 1.88s (exit 0).
- `ruff check src/indodax_lab/backtest/__init__.py src/indodax_lab/risk/engine.py tests/architecture/test_decision_contract_ownership.py` → all checks passed (exit 0).
- `python -m pytest -q` → 941 passed, 2 skipped (platform-dependent symlink/Linux `/proc`), 0 failed in 37.71s (exit 0).
- `git diff --check` → exit 0.
- `python -m compileall -q src` → exit 0.

No dependency was installed into the shared/base environment; all required declared research dependencies were confirmed present in the dedicated research runtime.

## Compatibility and migration

No schema, field, default, validator, persistence, venue, accounting, or execution behavior changed. Existing `indodax_lab.backtest.events.SignalIntent` imports remain valid and resolve to the shared class. New code should import `indodax_lab.contracts.decision.SignalIntent` directly.

## Safety and scope checks

- No credentials, real order authority, network calls, runtime databases, or production activation were used.
- No `main` or `dev` branch change, merge, push, or deployment.
- No product-path files outside the declared RP-01 source/test scope were modified.
- `dashboard.pen` and `DESIGN.md` were preserved and untouched.

## Reviewer and coordinator decision

- Independent reviewer `/root/architecture_doc_review` returned PASS on exact code SHA `5d9629e` with no Critical, Important, or Minor findings.
- Delivery coordinator verified the full-suite environment execution (941 passed, 0 failed) at code SHA `5d9629e`.
- Gate status: DONE. RP-01 is marked DONE in sprint-manifest.json, unlocking downstream RW0-01.
