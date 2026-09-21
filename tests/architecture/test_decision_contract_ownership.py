"""Architecture invariants for the shared SignalIntent contract."""

import ast
import os
from pathlib import Path
import subprocess
import sys


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


def test_shared_signal_intent_import_works_in_fresh_process() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("src").resolve())
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "from indodax_lab.contracts.decision import SignalIntent; print(SignalIntent.__name__)",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SignalIntent"


def test_legacy_signal_intent_import_works_in_fresh_process() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("src").resolve())
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "from indodax_lab.backtest.events import SignalIntent; print(SignalIntent.__name__)",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SignalIntent"
