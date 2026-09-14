"""Run or safely inspect the public-only Indodax market-stream collector."""

from __future__ import annotations

import argparse
import asyncio
import random
import signal
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from indodax_lab.data.indodax_stream import (
    AppendOnlyStreamWriter,
    CollectorConfig,
    PublicMarketCollector,
    StreamTransportClosed,
)
from indodax_lab.data.manifest import canonical_json_bytes
from indodax_lab.data.stream_protocol import BookSessionProtocol


class _WebsocketsTransport:
    def __init__(
        self,
        connection: Any,
        *,
        closed_error_types: tuple[type[BaseException], ...],
    ) -> None:
        self._connection = connection
        self._closed_error_types = closed_error_types

    async def send(self, message: str) -> None:
        try:
            await self._connection.send(message)
        except self._closed_error_types as error:
            raise StreamTransportClosed("public WebSocket closed while sending") from error

    async def receive(self, *, timeout: float) -> str | bytes:
        try:
            return await asyncio.wait_for(self._connection.recv(), timeout=timeout)
        except self._closed_error_types as error:
            raise StreamTransportClosed("public WebSocket closed while receiving") from error

    async def close(self) -> None:
        try:
            await self._connection.close()
        except self._closed_error_types:
            return


async def _connect(endpoint: str) -> _WebsocketsTransport:
    """Import the optional research-only client only at the real transport boundary."""
    import websockets
    from websockets.exceptions import WebSocketException

    try:
        connection = await websockets.connect(endpoint, max_queue=1, ping_interval=None)
    except WebSocketException as error:
        raise StreamTransportClosed("public WebSocket connection failed") from error
    return _WebsocketsTransport(
        connection,
        closed_error_types=(WebSocketException,),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--pair", default="btc_idr")
    parser.add_argument("--endpoint", default="wss://ws3.indodax.com/ws/")
    parser.add_argument("--public-token")
    parser.add_argument("--heartbeat-timeout", type=float, default=30.0)
    parser.add_argument("--max-batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    token = args.public_token or "dry-run-public-token"
    try:
        config = CollectorConfig(
            endpoint=args.endpoint,
            pair=args.pair,
            public_token=token,
            heartbeat_timeout=args.heartbeat_timeout,
        )
        if args.max_batch_size <= 0:
            raise ValueError("max batch size must be positive")
    except ValueError as error:
        parser.error(str(error))
    symbol = config.pair.replace("_", "")
    if args.dry_run:
        safe = {
            "mode": "dry-run",
            "public_only": True,
            "endpoint": config.endpoint,
            "pair": config.pair,
            "channels": [
                f"market:trade-activity-{symbol}",
                f"market:order-book-{symbol}",
            ],
            "heartbeat_timeout": config.heartbeat_timeout,
            "max_batch_size": args.max_batch_size,
        }
        print(canonical_json_bytes(safe).decode("utf-8"))
        return 0
    if args.public_token is None:
        parser.error("--public-token is required unless --dry-run is used")
    return asyncio.run(_run(config, args.data_root, args.max_batch_size))


async def _run(config: CollectorConfig, data_root: Path, max_batch_size: int) -> int:
    writer = AppendOnlyStreamWriter(data_root, max_batch_size=max_batch_size)
    protocol = BookSessionProtocol(
        pair=config.pair,
        session_id_factory=lambda: f"indodax-book-{uuid.uuid4().hex}",
    )
    collector = PublicMarketCollector(
        config=config,
        writer=writer,
        protocol=protocol,
        connector=_connect,
        clock=lambda: datetime.now(tz=UTC),
        sleeper=asyncio.sleep,
        random_value=random.random,
    )
    loop = asyncio.get_running_loop()
    shutdown_task: asyncio.Task[None] | None = None

    def request_shutdown() -> None:
        nonlocal shutdown_task
        if shutdown_task is None:
            shutdown_task = asyncio.create_task(collector.shutdown())

    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, request_shutdown)
    try:
        await collector.run()
    finally:
        if shutdown_task is not None:
            await shutdown_task
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
