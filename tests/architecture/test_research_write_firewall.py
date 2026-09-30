"""RP-05-AC4: research transitive imports expose no real writer.

Static transitive-closure check over the research runtime modules plus a
fresh-interpreter import check and a compositional no-credential check.
No network, no credentials, no live modules imported here either.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path("src") / "indodax_lab"

# Research runtime entry modules: everything a research composition may pull.
RESEARCH_ENTRIES = [
    "runtime.composition",
    "runtime.kernel",
    "runtime.candidate",
    "runtime.exits",
    "market.event_feed",
    "execution.simulator_venue",
    "execution.shadow_venue",
    "execution.state_store",
    "execution.oms",
]

# Modules that confer real-venue write authority. None of these may appear in
# the transitive import closure of a research entry module.
LIVE_WRITER_MODULES = {
    "indodax_lab.execution.indodax_trading",
}

WRITER_ATTR_MARKERS = ("_api_key", "_secret_key", "submit_live_order", "place_live_order")


def _module_file(dotted: str) -> Path | None:
    rel = Path(*dotted.split("." ))
    for candidate in (SRC_ROOT / f"{rel}.py", SRC_ROOT / rel / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _local_imports(path: Path, package: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                prefix = ".".join(base[: len(base) - node.level + 1])
                if node.module:
                    found.add(f"{prefix}.{node.module}")
                else:
                    found.update(f"{prefix}.{alias.name}" for alias in node.names)
            elif node.module:
                found.add(node.module)
    return {name for name in found if name.startswith("indodax_lab")}


def _closure(entries: list[str]) -> set[str]:
    seen: set[str] = set()
    stack = [f"indodax_lab.{entry}" for entry in entries]
    while stack:
        dotted = stack.pop()
        if dotted in seen:
            continue
        seen.add(dotted)
        path = _module_file(dotted.replace("indodax_lab.", "", 1))
        if path is None:
            continue
        package = dotted.rpartition(".")[0]
        for imported in _local_imports(path, package):
            if imported not in seen and _module_file(
                imported.replace("indodax_lab.", "", 1)
            ) is not None:
                stack.append(imported)
    return seen


def test_rp_05_4_transitive_imports_expose_no_live_writer() -> None:
    """RP-05-AC4: no research entry transitively imports a live writer."""
    closure = _closure(RESEARCH_ENTRIES)
    assert closure, "import closure must be non-empty (resolver broken otherwise)"
    assert "indodax_lab.runtime.kernel" in closure
    assert "indodax_lab.execution.simulator_venue" in closure
    assert len(closure) > 10, f"closure suspiciously small: {sorted(closure)}"
    violations = sorted(closure & LIVE_WRITER_MODULES)
    assert violations == [], f"research modules reach live writers: {violations}"


def test_rp_05_4_fresh_interpreter_imports_no_live_trading() -> None:
    """RP-05-AC4: importing research runtimes in a fresh process pulls no live module."""
    entries = ",".join(f"indodax_lab.{entry}" for entry in RESEARCH_ENTRIES)
    code = (
        "import sys; "
        f"import {entries}; "
        "live = [m for m in sys.modules if m == 'indodax_lab.execution.indodax_trading']; "
        "assert not live, live; "
        "print('NO_LIVE_WRITER_IMPORT_OK')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd="."
    )
    assert proc.returncode == 0, proc.stderr
    assert "NO_LIVE_WRITER_IMPORT_OK" in proc.stdout
