# LUNA-NEXT — RP-01 only

## TASK ID

RP-01 — Shared SignalIntent ownership with compatibility.

Current scheduling status: BLOCKED until DOC-01 independent review passes and coordinator marks RP-01 READY. Read the manifest at execution time; this handoff is not a permission bypass.

## OBJECTIVE

Move the existing SignalIntent class from backtest-owned source to a shared decision-contract module, preserving the identical class object at the legacy import and identical validation/serialization/defaults. This is ownership groundwork, not a claim that runtimes are unified.

## ARCHITECTURAL CONTEXT

Frozen two-system model requires common decision semantics. All runtime paths already use this class; duplicating it would create new drift. Read frozen docs, ADR-005, CONTRACTS.md, RUNTIME-PARITY.md and the RP-01 sprint Required Reading. No candidate/risk/ledger behavior changes belong here.

## ALLOWED SCOPE

One class definition move, a compatibility re-export, import-only canonical consumer edits, architecture/characterization tests and scoped handoff documentation.

## DO NOT TOUCH

MarketBar/ExecutionResult semantics; SignalIntent fields/defaults/validators; risk or strategy parameters; accounting; DB schemas; venue code behavior; legacy flat bot; immutable artifacts; main; credentials; running services; historical evidence.

## PRECONDITIONS

Manifest RP-01 READY; DOC-01 independently approved; BASE-01 historical DONE retained; one LUNA owner and independent final reviewer named; isolated `feat/rp-01-shared-signalintent-ownership-with-compatibility` worktree from reviewed documentation branch lineage. Inspect status/worktrees before edits. Install no dependencies into a shared environment.

## IMPLEMENTATION STEPS

1. Record base SHA and consumer list with `rg -n 'SignalIntent' src/indodax_lab tests`. Inspect aliases/import groupings rather than replacing whole modules blindly.
2. Create the architecture test below first. It must fail because the current AST declares SignalIntent in backtest/events.py, not because a new module cannot import.

```python
import ast
from pathlib import Path

def test_signal_intent_has_one_shared_owner():
    owners = []
    for path in Path("src/indodax_lab").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        if any(isinstance(node, ast.ClassDef) and node.name == "SignalIntent"
               for node in tree.body):
            owners.append(path.as_posix())
    assert owners == ["src/indodax_lab/contracts/decision.py"]
```

3. Run `python -m pytest tests/architecture/test_decision_contract_ownership.py -q`; expected behavioral RED lists the old path.
4. Add characterization tests against the existing legacy import before moving it. Use this golden BUY vector; also test SELL with explicit MAKER/GTC/limit/stop/TP values. Freeze expected serialized fields from the current schema, not by comparing two calls to the same new implementation.

```python
from datetime import UTC, datetime
from decimal import Decimal
import pytest
from indodax_lab.backtest.events import SignalIntent

def test_existing_signal_serialization():
    value = SignalIntent(intent_id="intent-1",
        decision_ts=datetime(2026, 9, 21, tzinfo=UTC), pair="btc_idr",
        side="buy", desired_qty=Decimal("0.0100"))
    assert value.model_dump(mode="json") == {
        "intent_id": "intent-1", "decision_ts": "2026-09-21T00:00:00Z",
        "pair": "btc_idr", "side": "buy", "desired_qty": "0.0100",
        "limit_price": None, "stop_loss": None, "take_profit": None,
        "role_preference": "taker", "strategy_id": "default_strat",
        "time_in_force": "IOC",
    }

@pytest.mark.parametrize("qty", ["0", "-1", "NaN", "Infinity"])
def test_invalid_quantity_rejected(qty):
    with pytest.raises(ValueError, match="POSITIVE_DESIRED_QTY_REQUIRED"):
        SignalIntent(intent_id="bad", decision_ts=datetime(2026, 9, 21, tzinfo=UTC),
                     pair="btc_idr", side="buy", desired_qty=qty)
```

Add naive timestamp rejection and positive/invalid optional prices. Verify enum wire values in `backtest/costs.py` before executing this fixture; if baseline differs, record and correct the golden characterization before moving the class, never change the class to fit an assumed fixture.

5. Create `contracts/decision.py` with the existing class body unchanged and only its required imports plus a local UTC helper with identical validation behavior. Keep backtest/events.py's helper for MarketBar. Re-export with `from indodax_lab.contracts.decision import SignalIntent as SignalIntent`. Do not create a subclass or copy.
6. Change canonical consumer SignalIntent imports to the new module; retain other names imported from backtest.events. Enumerate actual changed paths in handoff. No new dependency on concrete venue clients. Existing dependency on OrderRole/OrderSide in backtest.costs remains until a separately scoped extraction.
7. Add identity assertion: `from indodax_lab.contracts.decision import SignalIntent as Shared; assert Shared is SignalIntent`. Verify old and new imports in a fresh Python process to detect cycles.
8. Run focused tests, all architecture tests, full product suite and diff check below. Commit only scoped files. Submit exact code SHA and independent reviewer packet; do not self-mark DONE.

## FILES

- Create `src/indodax_lab/contracts/decision.py`.
- Modify `src/indodax_lab/backtest/events.py` and canonical consumer imports identified in step 1.
- Create `tests/architecture/test_decision_contract_ownership.py` and `tests/unit/lab/test_decision_contract_compatibility.py`.
- Record `docs/sprints/handoffs/RP-01-HANDOFF.md` only after actual work; no prewritten PASS.

## TESTS

```text
python -m pytest tests/architecture/test_decision_contract_ownership.py -q
python -m pytest tests/unit/lab/test_decision_contract_compatibility.py tests/architecture -q
python -m pytest -q
git diff --check
```

Run repository-required lint on changed canonical files. Use isolated declared core/research/CPU-DL environment; unavailable required dependencies or skipped required tests block PASS. Never run the shadow CLI or real HTTP to verify a contract move.

## ACCEPTANCE CHECKS

One class definition; old/new import object identity; exact BUY/SELL serialization; unchanged UTC/Decimal/optional price rejection; unchanged IOC/TAKER/default strategy; all consumers import successfully; no runtime logic diff beyond class placement/imports.

## EXPECTED OUTPUT

One independently reviewable committed unit and exact-SHA handoff with observed RED/GREEN, environment and command results. Manifest stays REVIEW until reviewer PASS. Coordinator then records completion and prepares only the next genuinely eligible task.

## STOP CONDITIONS

Dependencies not DONE; no independent review owner; dirty unrelated work; baseline serialization contradicts documented compatibility; import cycles requiring wider extraction; any proposed schema/default behavior change; required environment unavailable. Preserve WIP and report the concrete blocker.
