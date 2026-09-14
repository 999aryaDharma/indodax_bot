"""CLI for the deterministic, fail-closed candle snapshot quality gate."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO

from indodax_lab.data.manifest import canonical_json_bytes
from indodax_lab.data.quality import InvalidValidationWindowError, failure_report
from indodax_lab.data.sentry import validate_snapshot, validate_snapshot_id


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return parsed.astimezone(UTC)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _argument_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Validate immutable Indodax candle snapshot quality")
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--from", dest="expected_start", required=True, type=_parse_utc)
    parser.add_argument("--to", dest="expected_end", required=True, type=_parse_utc)
    parser.add_argument("--as-of", required=True, type=_parse_utc)
    parser.add_argument("--max-final-bar-age-seconds", type=int)
    parser.add_argument("--approve-warnings", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    """Print exactly one structured report and return the documented decision exit code."""
    try:
        args = _argument_parser().parse_args(argv)
        if args.max_final_bar_age_seconds is not None and args.max_final_bar_age_seconds < 0:
            raise ValueError("max final bar age must be non-negative")
        if args.expected_end <= args.expected_start:
            raise ValueError("expected end must be after expected start")
        validate_snapshot_id(args.snapshot_id)
    except (ValueError, TypeError):
        _write(failure_report("INVALID_INVOCATION"), stdout)
        return 4
    try:
        result = validate_snapshot(
            args.data_root,
            args.snapshot_id,
            expected_start=args.expected_start,
            expected_end=args.expected_end,
            as_of=args.as_of,
            approve_warnings=args.approve_warnings,
            max_final_bar_age=(
                timedelta(seconds=args.max_final_bar_age_seconds)
                if args.max_final_bar_age_seconds is not None
                else None
            ),
        )
    except InvalidValidationWindowError:
        _write(failure_report("INVALID_INVOCATION"), stdout)
        return 4
    _write(result.report, stdout)
    return {"PASS": 0, "WARN": 2, "FAIL": 3}[result.report.status]


def _write(report, stdout: TextIO) -> None:
    stdout.write(canonical_json_bytes(report.to_dict()).decode("utf-8") + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
