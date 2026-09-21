"""Minimal no-write Indodax private API smoke check.

Run with:
  INDODAX_VIEW_API_KEY=... INDODAX_VIEW_SECRET_KEY=... \
  python -m indodax_lab.execution.read_only_smoke btc_idr eth_idr

The command never prints keys, balances, order IDs, client order IDs, quantities, or fills.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from indodax_lab.execution.indodax_readonly import (
    IndodaxReadOnlyClient,
    VenueReadError,
)


def run_read_only_smoke(
    client: IndodaxReadOnlyClient,
    pairs: Sequence[str],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Probe supported private read paths while returning structural metadata only."""

    if not pairs:
        raise ValueError("SMOKE_PAIRS_REQUIRED")
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() != timedelta(0):
        raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED:now")

    account = client.get_account_snapshot()
    clock_skew_ms = int((current - account.server_time).total_seconds() * 1000)
    pair_results: dict[str, dict[str, bool]] = {}

    start_ms = int((current - timedelta(minutes=5)).timestamp() * 1000)
    end_ms = int(current.timestamp() * 1000)
    for pair in pairs:
        client.get_open_orders(pair)
        client.get_order_history(
            pair,
            start_time_ms=start_ms,
            end_time_ms=end_ms,
            limit=10,
            sort="desc",
        )
        client.get_trade_fills(
            pair,
            start_time_ms=start_ms,
            end_time_ms=end_ms,
            limit=10,
            sort="desc",
        )
        pair_results[pair] = {
            "open_orders_ok": True,
            "order_history_v2_ok": True,
            "trade_history_v2_ok": True,
        }

    return {
        "ok": True,
        "account_snapshot_ok": True,
        "clock_skew_ms": clock_skew_ms,
        "pairs": pair_results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Indodax private view-only API paths without trading."
    )
    parser.add_argument(
        "pairs",
        nargs="+",
        help="Canonical pairs, for example btc_idr eth_idr",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    api_key = os.environ.get("INDODAX_VIEW_API_KEY", "")
    secret_key = os.environ.get("INDODAX_VIEW_SECRET_KEY", "")
    if not api_key or not secret_key:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "INDODAX_VIEW_CREDENTIALS_MISSING",
                },
                sort_keys=True,
            )
        )
        return 2

    client = IndodaxReadOnlyClient(api_key=api_key, secret_key=secret_key)
    try:
        result = run_read_only_smoke(client, args.pairs)
    except (VenueReadError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
