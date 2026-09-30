"""Research shadow-agent CLI: fake-feed replay plus read-only queries (RW5-01).

Research-only operator tool over an ``AgentFactory`` root. ``list`` and
``show`` are read-only queries. ``replay`` integrates a fake canonical feed
from a JSON event file and routes it through the factory into RUNNING
agents; replayed agents with no registered behavior advance coverage with
no orders (the CLI never invents strategies and never resolves live
venues). No network, no credentials, no production paths.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO


def _factory_for(root: Path):
    from indodax_lab.paper.agents import AgentFactory

    def _resolve(ref):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            candidate_digest=ref.sha256, plan_digest=f"plan_{ref.sha256[:8]}"
        )

    return AgentFactory(root, candidate_resolver=_resolve)


def _parse_event(raw: dict) -> object:
    from indodax_lab.backtest.events import MarketBar
    from indodax_lab.runtime.candidate import CanonicalMarketEvent

    close_time = raw["event_time"]
    from datetime import datetime

    ts = datetime.fromisoformat(close_time)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    price = str(raw.get("price", "100"))
    bar = MarketBar(
        pair=str(raw.get("pair", "btc_idr")),
        open_time=ts - timedelta(minutes=1),
        close_time=ts,
        open=Decimal(price),
        high=Decimal(price),
        low=Decimal(price),
        close=Decimal(price),
        base_volume=Decimal("1"),
        quote_volume=Decimal(price),
    )
    return CanonicalMarketEvent(
        event_id=str(raw["event_id"]),
        feed_id=str(raw.get("feed_id", "feed-p")),
        sequence=int(raw["sequence"]),
        pair=str(raw.get("pair", "btc_idr")),
        event_time=ts,
        available_at=ts,
        observation=bar,
        quality_ref=None,
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research shadow-agent operator tool.")
    parser.add_argument("--root", type=Path, required=True, help="AgentFactory root")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("list", help="List agents (read-only)")
    show = sub.add_parser("show", help="Show one agent record (read-only)")
    show.add_argument("--agent-id", required=True)
    show.add_argument("--version", default="v1")
    replay = sub.add_parser("replay", help="Replay a fake feed file into RUNNING agents")
    replay.add_argument("--feed-file", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    parser = _argument_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 3

    factory = _factory_for(args.root)

    if args.subcommand == "list":
        stdout.write(
            json.dumps([r.model_dump(mode="json") for r in factory.list_agents()], indent=2)
            + "\n"
        )
        return 0

    if args.subcommand == "show":
        from indodax_lab.paper.agents import AgentError

        try:
            record = factory.get(args.agent_id, args.version)
        except AgentError as exc:
            stdout.write(json.dumps({"ok": False, "error": str(exc)}) + "\n")
            return 1
        stdout.write(json.dumps(record.model_dump(mode="json"), indent=2) + "\n")
        return 0

    if args.subcommand == "replay":
        from indodax_lab.paper.agents import AgentError

        try:
            raw_events = json.loads(args.feed_file.read_text(encoding="utf-8"))
        except OSError as exc:
            stdout.write(json.dumps({"ok": False, "error": f"FEED_FILE_UNREADABLE:{exc}"}) + "\n")
            return 1
        results: list[dict] = []
        for raw in raw_events:
            try:
                event = _parse_event(raw)
            except (KeyError, ValueError) as exc:
                results.append({"event": raw.get("event_id"), "error": f"FEED_EVENT_INVALID:{exc}"})
                continue
            for record in factory.list_agents():
                if record.lifecycle != "RUNNING":
                    continue
                try:
                    step = factory.process(record.agent_id, event, record.version)
                    results.append(
                        {"agent_id": record.agent_id, "event_id": event.event_id,
                         "status": step.status, "cursor": step.cursor}
                    )
                except AgentError as exc:
                    results.append(
                        {"agent_id": record.agent_id, "event_id": event.event_id,
                         "error": str(exc)}
                    )
        stdout.write(json.dumps({"ok": True, "results": results}, indent=2) + "\n")
        return 0

    return 3


if __name__ == "__main__":
    sys.exit(main())
