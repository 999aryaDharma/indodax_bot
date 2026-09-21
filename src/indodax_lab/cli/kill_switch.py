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
    subparsers.add_parser("clear", help="Clear/disarm emergency kill switch")

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
        if sentinel_path.exists():
            sentinel_path.unlink()
            cleared = True
        else:
            cleared = False

        output = {
            "ok": True,
            "action": "CLEARED",
            "was_active": cleared,
            "sentinel_path": str(sentinel_path),
        }
        stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
        return 0

    return 3


if __name__ == "__main__":
    sys.exit(main())
