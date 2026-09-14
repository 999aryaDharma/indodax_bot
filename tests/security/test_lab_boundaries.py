"""Security boundary and attack resistance verification (QA-02).

Guarantees:
1. QA-02-AC0: Full security boundary audit proves secret, artifact loader, and destructive paths are closed (test_qa_02_valid_contract).
2. QA-02-AC1: Path traversal attacks and malicious/tampered artifacts are strictly rejected fail-closed (test_qa_02_contract_1).
3. QA-02-AC2: No trade or withdrawal credentials exist or are permitted in lab execution (test_qa_02_contract_2).
4. QA-02-AC3: Telegram chat allowlists are strictly enforced, rejecting unauthorized chats without data leakage (test_qa_02_contract_3).
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from indodax_lab.security.boundary import (
    PathTraversalError,
    SecurityAuditReport,
    SecurityAuditRunner,
    SecurityViolationError,
    audit_no_trade_withdraw_keys,
    safe_resolve_artifact_path,
    verify_artifact_bytes_safe,
)
from indodax_lab.reporting.telegram import (
    ChampionStatus,
    ReadOnlyTelegramReporter,
    ResearchHoldingsStatus,
    ResearchQueueStatus,
    SystemHealthStatus,
    UnauthorizedChatError,
)


def test_qa_02_valid_contract(tmp_path: Path) -> None:
    """AC0: Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate."""
    runner = SecurityAuditRunner(base_dir=tmp_path)
    report: SecurityAuditReport = runner.run_audit(
        env_dict={"ENVIRONMENT": "paper_research", "RESEARCH_DATA_ROOT": str(tmp_path)},
    )

    assert report.status == "PASSED"
    assert report.critical_findings_count == 0
    assert report.checks_executed >= 3
    assert "SECRET_BOUNDARY_VERIFIED" in report.verified_checks
    assert "ARTIFACT_LOADER_VERIFIED" in report.verified_checks
    assert "TELEGRAM_ALLOWLIST_VERIFIED" in report.verified_checks


def test_qa_02_contract_1(tmp_path: Path) -> None:
    """AC1: Traversal dan malicious artifact ditolak."""
    base_dir = tmp_path / "artifacts"
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Path traversal attacks must raise PathTraversalError
    traversal_payloads = [
        "../../etc/passwd",
        r"..\..\windows\win.ini",
        "nested/../../../secret.env",
        "/etc/shadow",
        r"C:\Windows\System32\cmd.exe",
    ]
    for target in traversal_payloads:
        with pytest.raises(PathTraversalError):
            safe_resolve_artifact_path(base_dir=base_dir, target_subpath=target)

    # 2. Malicious pickle payload must be rejected fail-closed
    # Python pickle opcode: b"c__builtin__\nglobals\n(t." or b"\x80\x03cposix\nsystem\n..."
    pickle_payload = b"\x80\x04\x95\x1e\x00\x00\x00\x00\x00\x00\x00\x8c\x08builtins\x94\x8c\x04eval\x94\x93\x94."
    with pytest.raises(SecurityViolationError) as exc_info:
        verify_artifact_bytes_safe(pickle_payload)
    assert "PICKLE_FORBIDDEN" in str(exc_info.value)

    # 3. Valid JSON artifact payload must pass
    valid_json_payload = b'{"model_id": "M01", "version": "1.0.0", "weights": [0.1, 0.2]}'
    assert verify_artifact_bytes_safe(valid_json_payload) is True


def test_qa_02_contract_2() -> None:
    """AC2: Tidak ada trade-withdraw credentials."""
    # 1. Environment containing forbidden trading or withdrawal credentials must fail audit
    dirty_env = {
        "INDODAX_API_KEY": "read_only_key_123",
        "INDODAX_TRADE_KEY": "secret_trade_key_forbidden",
    }
    with pytest.raises(SecurityViolationError) as exc_info:
        audit_no_trade_withdraw_keys(dirty_env)
    assert "FORBIDDEN_CREDENTIALS" in str(exc_info.value)
    assert "TRADE_KEY" in str(exc_info.value)

    withdrawal_env = {
        "INDODAX_WITHDRAWAL_SECRET": "forbidden_withdrawal_secret",
    }
    with pytest.raises(SecurityViolationError) as exc_info2:
        audit_no_trade_withdraw_keys(withdrawal_env)
    assert "FORBIDDEN_CREDENTIALS" in str(exc_info2.value)

    # 2. Clean research environment passes cleanly
    clean_env = {
        "ENVIRONMENT": "paper_research",
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
        "TELEGRAM_CHAT_ID": "12345678",
    }
    findings = audit_no_trade_withdraw_keys(clean_env)
    assert len(findings) == 0


def test_qa_02_contract_3() -> None:
    """AC3: Allowlist Telegram ditegakkan."""
    allowed_chat_id = "11223344"
    unauthorized_chat_id = "99887766"

    reporter = ReadOnlyTelegramReporter(
        bot_token="test_token_123",
        allowed_chat_ids=[allowed_chat_id],
    )

    # Unauthorized access is rejected with UnauthorizedChatError without leaking any data
    with pytest.raises(UnauthorizedChatError):
        reporter.get_status_report(
            chat_id=unauthorized_chat_id,
            queue=ResearchQueueStatus(),
            champion=ChampionStatus(champion_id="m01", champion_version="1.0.0"),
            health=SystemHealthStatus(),
            holdings=ResearchHoldingsStatus(),
        )

    # Allowlisted chat succeeds
    report = reporter.get_status_report(
        chat_id=allowed_chat_id,
        queue=ResearchQueueStatus(),
        champion=ChampionStatus(champion_id="m01", champion_version="1.0.0"),
        health=SystemHealthStatus(),
        holdings=ResearchHoldingsStatus(),
    )
    assert "Indodax Research Lab Status" in report
