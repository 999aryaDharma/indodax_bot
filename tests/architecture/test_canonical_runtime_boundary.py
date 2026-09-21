"""Architecture guard: canonical lab runtime must not depend on legacy flat modules."""

from __future__ import annotations

import ast
from pathlib import Path


CANONICAL_ROOT = Path("src/indodax_lab")
LEGACY_MODULES = {
    "config",
    "indodax_api",
    "main",
    "paper_accounting",
    "paper_trader",
    "position_tracker",
    "risk_manager",
    "signal_cache",
    "signal_logic",
    "signal_observer",
    "ta_processor",
    "telegram_bot",
}


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_canonical_runtime_does_not_import_legacy_flat_modules() -> None:
    violations: dict[str, list[str]] = {}
    for path in CANONICAL_ROOT.rglob("*.py"):
        legacy = sorted(_import_roots(path) & LEGACY_MODULES)
        if legacy:
            violations[path.as_posix()] = legacy

    assert violations == {}, (
        "Canonical indodax_lab code must not depend on legacy flat runtime modules: "
        f"{violations}"
    )
