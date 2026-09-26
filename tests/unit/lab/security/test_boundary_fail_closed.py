"""Fail-closed regression tests for the QA-02 security boundary.

Review findings covered:
- QA-02-F1 (Critical): the secret-scanning audit did not match the real credential
  names used by this project (``INDODAX_API_KEY``, ``INDODAX_SECRET_KEY``) nor the
  generic ``API_KEY``/``API_SECRET``/``SECRET_KEY``/``PRIVATE_KEY`` families, so
  actual API credentials passed the audit undetected.
- QA-02-F2 (Critical): enforcement used bare ``assert`` statements, which are
  stripped entirely under ``python -O`` / ``PYTHONOPTIMIZE``, so the security
  boundary silently vanished in an optimized production run.
- QA-02-F3 (Important): the audit report claimed to prove destructive paths were
  closed, but no destructive-path check was ever executed.

opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

from indodax_lab.security.boundary import (
    SecurityAuditRunner,
    SecurityViolationError,
    audit_no_trade_withdraw_keys,
    safe_resolve_artifact_path,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
BOUNDARY_MODULE = REPO_ROOT / "src" / "indodax_lab" / "security" / "boundary.py"


def test_qa_02_real_indodax_api_credentials_are_detected() -> None:
    """QA-02-F1: real Indodax API credentials must be caught, not waved through."""
    for offending_env in (
        {"INDODAX_API_KEY": "live_read_key"},
        {"INDODAX_SECRET_KEY": "live_signing_secret"},
    ):
        with pytest.raises(SecurityViolationError) as exc_info:
            audit_no_trade_withdraw_keys(offending_env)
        message = str(exc_info.value)
        assert "FORBIDDEN_CREDENTIALS" in message
        assert next(iter(offending_env)) in message


def test_qa_02_generic_credential_name_families_are_detected() -> None:
    """QA-02-F1: generic API/SECRET/PRIVATE key families must be caught."""
    for offending_key in (
        "API_KEY",
        "API_SECRET",
        "SECRET_KEY",
        "PRIVATE_KEY",
        "RESEARCH_API_KEY",
        "BINANCE_SECRET_KEY",
        "COINGECKO_PRIVATE_KEY",
    ):
        with pytest.raises(SecurityViolationError) as exc_info:
            audit_no_trade_withdraw_keys({offending_key: "value"})
        assert offending_key in str(exc_info.value)


def test_qa_02_audit_reports_every_offending_key_not_only_the_first() -> None:
    """QA-02-F1: a partial audit that names only the first key hides the rest."""
    dirty_env = {"INDODAX_API_KEY": "a", "INDODAX_TRADE_KEY": "b"}
    with pytest.raises(SecurityViolationError) as exc_info:
        audit_no_trade_withdraw_keys(dirty_env)
    message = str(exc_info.value)
    assert "INDODAX_API_KEY" in message
    assert "INDODAX_TRADE_KEY" in message


def test_qa_02_non_credential_environment_is_still_allowed() -> None:
    """QA-02-F1: widening detection must not reject legitimate non-credential env."""
    clean_env = {
        "ENVIRONMENT": "paper_research",
        "RESEARCH_DATA_ROOT": "/data/research",
        "TELEGRAM_BOT_TOKEN": "123456:ABC",
        "TELEGRAM_CHAT_ID": "12345678",
        "MODEL_SEED": "42",
    }
    assert audit_no_trade_withdraw_keys(clean_env) == []


def test_qa_02_boundary_module_enforces_without_assert_statements() -> None:
    """QA-02-F2: no security invariant may be enforced through a strippable ``assert``."""
    tree = ast.parse(BOUNDARY_MODULE.read_text(encoding="utf-8"))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert)
    ]
    assert not offenders, (
        f"{BOUNDARY_MODULE.name} enforces security invariants with assert() at lines "
        f"{offenders}; assert is removed under python -O / PYTHONOPTIMIZE, which silently "
        "disables the boundary in optimized production runs."
    )


def test_qa_02_assert_free_boundary_actually_blocks_a_broken_allowlist(tmp_path: Path) -> None:
    """QA-02-F2: the telegram allowlist check must fail closed via a real exception.

    Under ``python -O`` the previous ``assert`` based enforcement was stripped, so a
    reporter that authorizes every chat still produced a ``PASSED`` audit report.
    This test runs in a child interpreter with assertions disabled.
    """
    program = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "src")!r})

from indodax_lab.reporting.telegram import ReadOnlyTelegramReporter
import indodax_lab.security.boundary as boundary

runner = boundary.SecurityAuditRunner(base_dir=Path({str(tmp_path)!r}))

real_reporter = boundary.__dict__.get("ReadOnlyTelegramReporter")

class _LeakyReporter(ReadOnlyTelegramReporter):
    def is_authorized(self, chat_id):
        return True

import indodax_lab.reporting.telegram as tg
tg.ReadOnlyTelegramReporter = _LeakyReporter

try:
    report = runner.run_audit(env_dict={{"ENVIRONMENT": "paper_research"}})
except Exception as exc:
    print("RAISED:" + type(exc).__name__)
else:
    print("AUDIT_REPORT_STATUS:" + str(report.status))
"""
    completed = subprocess.run(
        [sys.executable, "-O", "-c", program],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    output = completed.stdout.strip()
    assert completed.returncode == 0, completed.stderr
    assert "AUDIT_REPORT_STATUS:PASSED" not in output, (
        "with assertions disabled (-O) a reporter that authorizes every chat still "
        f"produced a PASSED audit report: {output!r}"
    )
    assert "RAISED:SecurityViolationError" in output, (
        f"expected an explicit SecurityViolationError under -O, got {output!r}"
    )


def test_qa_02_audit_actually_verifies_the_destructive_path_boundary(tmp_path: Path) -> None:
    """QA-02-F3: the report may only claim the checks it really executed."""
    report = SecurityAuditRunner(base_dir=tmp_path).run_audit(
        env_dict={"ENVIRONMENT": "paper_research"},
    )
    assert report.status == "PASSED"
    assert "DESTRUCTIVE_PATH_BOUNDARY_VERIFIED" in report.verified_checks
    assert report.checks_executed == len(report.verified_checks) == 4


def test_qa_02_audit_reports_no_pass_when_the_traversal_guard_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QA-02-F3: a disabled traversal guard must not be reported as PASSED."""
    import indodax_lab.security.boundary as boundary

    monkeypatch.setattr(
        boundary,
        "safe_resolve_artifact_path",
        lambda base_dir, target_subpath: (Path(base_dir) / "escaped").resolve(),
    )
    with pytest.raises(SecurityViolationError):
        boundary.SecurityAuditRunner(base_dir=tmp_path).run_audit(
            env_dict={"ENVIRONMENT": "paper_research"},
        )


def test_qa_02_destructive_escape_target_is_still_rejected(tmp_path: Path) -> None:
    """QA-02-F3 guard check: the escape target used by the audit must be refused."""
    from indodax_lab.security.boundary import PathTraversalError

    with pytest.raises(PathTraversalError):
        safe_resolve_artifact_path(tmp_path, "../../../etc/passwd")


# Actor for every line this file contributes to review evidence:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
