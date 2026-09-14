"""Official offset-recovery coordinator for reliable public order-book sessions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from .stream_protocol import (
    BookSessionProtocol,
    InvalidPublicStreamMessage,
    ProtocolResult,
)


@dataclass(frozen=True)
class QuarantinedGap:
    """Exact missing publication window from one closed book session."""

    book_session_id: str
    pair: str
    channel: str
    missing_offset_start: int
    missing_offset_end: int
    observed_offset: int
    last_reliable_offset: int
    detected_at: datetime
    gap_reason: str
    abandonment_reason: str


@dataclass(frozen=True)
class OutstandingRecovery:
    request_id: int
    book_session_id: str
    pair: str
    channel: str


class BookRecoveryCoordinator:
    """Build official recovery requests and fail closed to a new session."""

    def __init__(
        self,
        protocol: BookSessionProtocol,
        *,
        request_id_factory: Callable[[], int],
    ) -> None:
        self._protocol = protocol
        self._request_id_factory = request_id_factory
        self._outstanding: OutstandingRecovery | None = None

    def start(self) -> dict[str, object]:
        """Enter recovery and request publications after the durable checkpoint offset."""
        if self._protocol.last_offset is None:
            raise RuntimeError("recovery has no acknowledged offset")
        if self._protocol.book_session_id is None:
            raise RuntimeError("recovery has no book session")
        if self._outstanding is not None:
            raise RuntimeError("a recovery request is already outstanding")
        self._protocol.start_recovery()
        symbol = self._protocol.pair.pair.replace("_", "")
        request_id = self._request_id_factory()
        channel = f"market:order-book-{symbol}"
        self._outstanding = OutstandingRecovery(
            request_id=request_id,
            book_session_id=self._protocol.book_session_id,
            pair=self._protocol.pair.pair,
            channel=channel,
        )
        return {
            "method": 1,
            "params": {
                "channel": channel,
                "recover": True,
                "offset": self._protocol.last_offset,
            },
            "id": request_id,
        }

    def is_matching_response(self, payload: object) -> bool:
        """Return true only for the exact currently outstanding recovery request."""
        return (
            self._outstanding is not None
            and isinstance(payload, Mapping)
            and payload.get("id") == self._outstanding.request_id
        )

    def apply(self, payload: object, *, ingested_at: datetime) -> ProtocolResult:
        """Restore eligibility only after the complete replay validates."""
        outstanding = self._outstanding
        if outstanding is None or not self.is_matching_response(payload):
            raise InvalidPublicStreamMessage("recovery response ID is not outstanding")
        if (
            self._protocol.book_session_id != outstanding.book_session_id
            or self._protocol.pair.pair != outstanding.pair
        ):
            raise InvalidPublicStreamMessage("recovery session or pair context changed")
        if not isinstance(payload, Mapping) or not isinstance(
            payload.get("result"), Mapping
        ):
            raise InvalidPublicStreamMessage("recovery response envelope is invalid")
        response_channel = payload["result"].get("channel")
        if response_channel is not None and response_channel != outstanding.channel:
            raise InvalidPublicStreamMessage("recovery response channel changed")
        try:
            result = self._protocol.apply_recovery(payload, ingested_at=ingested_at)
        except InvalidPublicStreamMessage as error:
            raise InvalidPublicStreamMessage(f"recovery response invalid: {error}") from error
        self._outstanding = None
        return result

    def prepare_failure(
        self, *, detected_at: datetime, abandonment_reason: str
    ) -> QuarantinedGap:
        """Describe an abandonment without clearing any retryable protocol state."""
        if (
            self._protocol.book_session_id is None
            or self._protocol.pending_gap is None
            or self._protocol.gap_reason is None
            or self._protocol.gap_observed_offset is None
            or self._protocol.last_offset is None
        ):
            raise RuntimeError("recovery gap context is incomplete")
        missing_start, missing_end = self._protocol.pending_gap
        pair = self._protocol.pair.pair
        return QuarantinedGap(
            book_session_id=self._protocol.book_session_id,
            pair=pair,
            channel=f"market:order-book-{pair.replace('_', '')}",
            missing_offset_start=missing_start,
            missing_offset_end=missing_end,
            observed_offset=self._protocol.gap_observed_offset,
            last_reliable_offset=self._protocol.last_offset,
            detected_at=detected_at,
            gap_reason=self._protocol.gap_reason,
            abandonment_reason=abandonment_reason,
        )

    def commit_failure(self, quarantine: QuarantinedGap) -> None:
        """Rotate the session only after the caller durably published this exact quarantine."""
        if (
            self._protocol.book_session_id != quarantine.book_session_id
            or self._protocol.pair.pair != quarantine.pair
            or self._protocol.pending_gap
            != (quarantine.missing_offset_start, quarantine.missing_offset_end)
            or self._protocol.gap_reason != quarantine.gap_reason
            or self._protocol.gap_observed_offset != quarantine.observed_offset
            or self._protocol.last_offset != quarantine.last_reliable_offset
        ):
            raise RuntimeError("quarantine no longer matches pending recovery state")
        self._protocol.abandon_gap()
        self._outstanding = None
