"""Operator CLI for emergency halt and kill switch management."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emergency Kill Switch operator control tool.")
    parser.add_argument(
        "--sentinel-path",
        type=Path,
        default=Path("emergency_kill_switch"),
        help="Path to kill switch sentinel file (default: ./emergency_kill_switch)",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: status
    subparsers.add_parser("status", help="Check kill switch status")

    # Subcommand: trip
    trip_parser = subparsers.add_parser("trip", help="Trip emergency kill switch immediately")
    trip_parser.add_argument(
        "--reason",
        default="OPERATOR_MANUAL_HALT",
        help="Reason code for audit log",
    )

    # Subcommand: clear
    clear_parser = subparsers.add_parser("clear", help="Clear/disarm emergency kill switch")
    clear_parser.add_argument(
        "--operator-id",
        default="OPERATOR_CLI",
        help="Operator ID performing the disarm (must be non-empty)",
    )
    clear_parser.add_argument(
        "--reason",
        default="OPERATOR_CLI_CLEARED",
        help="Audit reason for disarming kill switch (must be non-empty)",
    )
    clear_parser.add_argument(
        "--token",
        default=None,
        help="HMAC confirmation token if secret is configured",
    )
    clear_parser.add_argument(
        "--nonce",
        default=None,
        help="Token nonce for single-use bounded verification",
    )
    clear_parser.add_argument(
        "--evidence-path",
        type=Path,
        default=None,
        help="Path to health evidence JSON file (required for reset)",
    )
    clear_parser.add_argument(
        "--oms-db-path",
        type=Path,
        default=None,
        help="Optional path to OMS store to verify 0 UNKNOWN orders",
    )
    clear_parser.add_argument(
        "--reconcile-report-path",
        type=Path,
        default=None,
        help="Optional path to reconciliation report to verify health",
    )

    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    parser = _argument_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 3

    sentinel_path = args.sentinel_path

    if args.subcommand == "status":
        active = sentinel_path.exists()
        details = None
        if active:
            try:
                details = sentinel_path.read_text(encoding="utf-8").strip()
            except OSError:
                details = "UNREADABLE"

        output = {
            "ok": True,
            "kill_switch_active": active,
            "sentinel_path": str(sentinel_path),
            "details": details,
        }
        stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
        return 0

    if args.subcommand == "trip":
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        now_utc = datetime.now(UTC).isoformat()
        content = f"HALTED:{args.reason}:{now_utc}\n"
        sentinel_path.write_text(content, encoding="utf-8")

        output = {
            "ok": True,
            "action": "TRIPPED",
            "sentinel_path": str(sentinel_path),
            "reason": args.reason,
            "timestamp": now_utc,
        }
        stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
        return 0

    if args.subcommand == "clear":
        from indodax_lab.risk.engine import HealthEvidence, RiskEngine

        evidence: HealthEvidence | None = None
        if args.evidence_path is not None and args.evidence_path.exists():
            try:
                ev_data = json.loads(args.evidence_path.read_text(encoding="utf-8"))
                evidence = HealthEvidence(
                    timestamp_utc=datetime.fromisoformat(ev_data["timestamp_utc"]),
                    reconciliation_healthy=bool(ev_data.get("reconciliation_healthy", False)),
                    unknown_orders_count=int(ev_data.get("unknown_orders_count", 0)),
                    source=str(ev_data.get("source", "cli")),
                    signature=ev_data.get("signature"),
                )
            except Exception as e:
                output = {
                    "ok": False,
                    "action": "CLEAR_REJECTED",
                    "error": f"INVALID_HEALTH_EVIDENCE_FILE: {e}",
                    "sentinel_path": str(sentinel_path),
                }
                stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
                return 1
        elif (args.oms_db_path is not None and args.oms_db_path.exists()) or (
            args.reconcile_report_path is not None and args.reconcile_report_path.exists()
        ):
            from indodax_lab.execution.oms import OmsOrderState
            from indodax_lab.execution.oms_store import OmsStore

            unknown_count = 0
            if args.oms_db_path is not None and args.oms_db_path.exists():
                oms = OmsStore(args.oms_db_path)
                unknown_count = len(
                    [o for o in oms.load_nonterminal_orders() if o.state == OmsOrderState.UNKNOWN]
                )

            reconciliation_healthy = True
            report_ts = datetime.now(UTC)
            if args.reconcile_report_path is not None and args.reconcile_report_path.exists():
                try:
                    report_data = json.loads(args.reconcile_report_path.read_text(encoding="utf-8"))
                    if report_data.get("status") != "HEALTHY":
                        reconciliation_healthy = False
                    if "timestamp_utc" in report_data:
                        report_ts = datetime.fromisoformat(report_data["timestamp_utc"])
                except Exception:
                    reconciliation_healthy = False

            evidence = HealthEvidence(
                timestamp_utc=report_ts,
                reconciliation_healthy=reconciliation_healthy,
                unknown_orders_count=unknown_count,
                source="oms_reconcile_cli",
            )

        was_active = sentinel_path.exists()
        engine = RiskEngine(kill_switch_path=sentinel_path)

        try:
            engine.reset_kill_switch(
                operator_id=args.operator_id,
                reason=args.reason,
                evidence=evidence,
                confirmation_token=args.token,
                token_nonce=args.nonce,
            )
        except Exception as exc:
            output = {
                "ok": False,
                "action": "CLEAR_REJECTED",
                "error": str(exc),
                "sentinel_path": str(sentinel_path),
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 1

        output = {
            "ok": True,
            "action": "CLEARED",
            "was_active": was_active,
            "operator_id": args.operator_id,
            "reason": args.reason,
            "sentinel_path": str(sentinel_path),
        }
        stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
        return 0

    return 3


if __name__ == "__main__":
    sys.exit(main())
