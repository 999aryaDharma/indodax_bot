"""Architecture invariants for the shared SignalIntent contract."""

import ast
from pathlib import Path


def test_signal_intent_has_one_shared_owner() -> None:
    owners = []
    for path in Path("src/indodax_lab").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "SignalIntent"
            for node in tree.body
        ):
            owners.append(path.as_posix())

    assert owners == ["src/indodax_lab/contracts/decision.py"]


def test_legacy_and_shared_signal_intent_are_same_class() -> None:
    from indodax_lab.backtest.events import SignalIntent as LegacySignalIntent
    from indodax_lab.contracts.decision import SignalIntent

    assert SignalIntent is LegacySignalIntent
