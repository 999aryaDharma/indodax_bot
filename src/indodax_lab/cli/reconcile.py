"""Operator reconciliation CLI for durable fill-history and balance validation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO

from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.execution.fake_venue import DeterministicFakeVenue
from indodax_lab.execution.fill_ingestion import VenueFillIngester
from indodax_lab.execution.indodax_readonly import (
    IndodaxReadOnlyClient,
    VenueAccountSnapshot,
    VenueBalance,
    VenueReadError,
)
from indodax_lab.execution.read_only_reconciler import (
    PrivateReadOnlyReconciliationService,
)
from indodax_lab.execution.reconciliation_coordinator import (
    DurableReconciliationCoordinator,
)
from indodax_lab.execution.reconciliation_store import (
    ReconciliationCursorStore,
)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute a durable private reconciliation cycle against Indodax venue truth."
    )
    parser.add_argument(
        "--scope-id",
        default="indodax_main",
        help="Durable reconciliation cursor scope ID (default: indodax_main)",
    )
    parser.add_argument(
        "--pairs",
        default="btc_idr,eth_idr",
        help="Comma-separated list of canonical pairs (default: btc_idr,eth_idr)",
    )
    parser.add_argument(
        "--cursor-db",
        type=Path,
        default=Path("var/reconciliation_cursor.db"),
        help="Path to SQLite reconciliation cursor store (default: var/reconciliation_cursor.db)",
    )
    parser.add_argument(
        "--init-cursor-ms",
        type=int,
        default=None,
        help="Optional initial fill window start millisecond timestamp if cursor is uninitialized",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Optional ISO-8601 UTC timestamp of evaluation (default: UTC now)",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=1000,
        help="Maximum history records to fetch per pair (10-1000, default: 1000)",
    )
    parser.add_argument(
        "--auto-ingest",
        action="store_true",
        help="Automatically ingest venue fills into ledger before reconciliation",
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Run in offline drill mode using deterministic FakeVenueAdapter",
    )
    return parser


class _FakeReadOnlyClient:
    """Read-only adapter view wrapping DeterministicFakeVenue for testing/offline drills."""

    def __init__(self, fake_venue: DeterministicFakeVenue) -> None:
        self.fake_venue = fake_venue

    def get_account_snapshot(self) -> VenueAccountSnapshot:
        now = datetime.now(UTC)
        balances = {
            "idr": VenueBalance(
                currency="idr",
                available=Decimal("100000000"),
                hold=Decimal("0"),
            )
        }
        return VenueAccountSnapshot(
            server_time=now,
            balances=balances,
        )

    def get_open_orders(self, pair: str) -> tuple[Any, ...]:
        return ()

    def get_order_history(self, pair: str, **kwargs: Any) -> tuple[Any, ...]:
        return ()

    def get_trade_fills(self, pair: str, **kwargs: Any) -> tuple[Any, ...]:
        return ()


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    parser = _argument_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 3

    if args.as_of:
        try:
            eval_time = datetime.fromisoformat(args.as_of)
            if eval_time.tzinfo is None:
                eval_time = eval_time.replace(tzinfo=UTC)
            else:
                eval_time = eval_time.astimezone(UTC)
        except ValueError:
            stdout.write(
                json.dumps(
                    {"ok": False, "error": f"INVALID_AS_OF_TIMESTAMP:{args.as_of}"},
                    indent=2,
                )
                + "\n"
            )
            return 3
    else:
        eval_time = datetime.now(UTC)

    pairs = [p.strip().lower() for p in args.pairs.split(",") if p.strip()]
    if not pairs:
        stdout.write(json.dumps({"ok": False, "error": "NO_PAIRS_SPECIFIED"}, indent=2) + "\n")
        return 3

    cursor_store = ReconciliationCursorStore(args.cursor_db)
    cursor = cursor_store.load(args.scope_id)

    if cursor is None:
        if args.init_cursor_ms is not None:
            cursor = cursor_store.initialize(
                scope_id=args.scope_id,
                start_ms=args.init_cursor_ms,
                at=eval_time,
            )
        elif args.fake:
            default_start_ms = int((eval_time - timedelta(hours=1)).timestamp() * 1000)
            cursor = cursor_store.initialize(
                scope_id=args.scope_id,
                start_ms=default_start_ms,
                at=eval_time,
            )
        else:
            stdout.write(
                json.dumps(
                    {
                        "ok": False,
                        "status": "CURSOR_NOT_INITIALIZED",
                        "error": (
                            f"Cursor for scope '{args.scope_id}' does not exist. "
                            "Pass --init-cursor-ms <timestamp_ms> to initialize."
                        ),
                    },
                    indent=2,
                )
                + "\n"
            )
            return 3

    # Resolve venue client
    if args.fake:
        fake_venue = DeterministicFakeVenue()
        client = _FakeReadOnlyClient(fake_venue)
    else:
        api_key = os.environ.get("INDODAX_VIEW_API_KEY", "")
        secret_key = os.environ.get("INDODAX_VIEW_SECRET_KEY", "")
        if not api_key or not secret_key:
            stdout.write(
                json.dumps(
                    {
                        "ok": False,
                        "status": "BLOCKED_EXTERNAL",
                        "error": "INDODAX_VIEW_CREDENTIALS_MISSING",
                        "scope_id": args.scope_id,
                        "cursor_start_ms": cursor.next_start_ms,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            return 2
        client = IndodaxReadOnlyClient(api_key=api_key, secret_key=secret_key)

    service = PrivateReadOnlyReconciliationService(client=client)
    ledger = ResearchLedger(initial_cash=Decimal("100000000") if args.fake else Decimal("0"))
    fill_ingester = VenueFillIngester(ledger=ledger) if args.auto_ingest else None

    coordinator = DurableReconciliationCoordinator(
        service=service,
        cursor_store=cursor_store,
        scope_id=args.scope_id,
        fill_ingester=fill_ingester,
    )

    try:
        cycle_result = coordinator.run(
            ledger=ledger,
            tracked_pairs=pairs,
            expected_open_order_ids=set(),
            evaluation_time=eval_time,
            history_limit=args.history_limit,
            auto_ingest_fills=args.auto_ingest,
        )
    except (VenueReadError, ValueError, RuntimeError) as exc:
        stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "status": "RECONCILIATION_EXECUTION_ERROR",
                    "error": str(exc),
                },
                indent=2,
            )
            + "\n"
        )
        return 1

    report = cycle_result.report
    output = {
        "ok": report.healthy,
        "status": report.status.value,
        "scope_id": args.scope_id,
        "cursor_advanced": cycle_result.cursor_advanced,
        "cursor_before_revision": cycle_result.cursor_before.revision,
        "cursor_after_revision": cycle_result.cursor_after.revision,
        "cursor_next_start_ms": cycle_result.cursor_after.next_start_ms,
        "issues_count": len(report.issues),
        "issues": [
            {"code": issue.code, "detail": issue.detail, "blocking": issue.blocking}
            for issue in report.issues
        ],
    }
    stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    return 0 if report.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
