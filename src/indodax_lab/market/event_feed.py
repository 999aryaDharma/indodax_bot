"""Canonical market event feed with shared upstream polling (RP-04).

One upstream poll per stream serves N subscribers. Each subscriber holds a
bounded queue; when unpublished events overflow it, the subscriber receives an
explicit gap with a resumable cursor instead of silently skipped events.

Guarantees (CONTRACTS.md):
- ``EventFeed.subscribe(namespace, after_sequence)`` replays buffered events.
- Duplicate same-bytes delivery is replay; conflicting bytes never occur here
  because the feed serves immutable, content-addressed events.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from indodax_lab.runtime.candidate import CanonicalMarketEvent


class SubscriberGapError(Exception):
    """A subscriber fell behind its bounded queue (RP-04-AC1)."""

    def __init__(self, feed_id: str, resume_sequence: int, dropped: int) -> None:
        self.feed_id = feed_id
        self.resume_sequence = resume_sequence
        self.dropped = dropped
        super().__init__(
            f"GAP_DETECTED: subscriber of '{feed_id}' dropped {dropped} event(s); "
            f"resume after sequence {resume_sequence}"
        )


UpstreamSource = Callable[[str, int], list[CanonicalMarketEvent]]
"""Poll new events for ``feed_id`` with sequence strictly above ``after_sequence``."""


@dataclass
class _Subscriber:
    namespace: str
    cursor: int
    queue: deque = field(default_factory=deque)
    gap: SubscriberGapError | None = None


class EventFeed:
    """Shared fan-out feed over one upstream poll per stream (RP-04-AC0)."""

    def __init__(
        self,
        source: UpstreamSource,
        *,
        max_queue: int = 1000,
        feed_id: str = "stream-a",
    ) -> None:
        if max_queue < 1:
            raise ValueError("EVENT_FEED_MAX_QUEUE_INVALID: max_queue must be >= 1")
        self._source = source
        self._max_queue = max_queue
        self._feed_id = feed_id
        self._buffer: list[CanonicalMarketEvent] = []
        self._polled_once = False
        self._subscribers: list[_Subscriber] = []

    def poll(self, feed_id: str | None = None) -> list[CanonicalMarketEvent]:
        """Poll upstream once per stream and fan out to subscriber queues."""
        target = feed_id or self._feed_id
        after = self._buffer[-1].sequence if self._buffer else 0
        fresh = list(self._source(target, after))
        for event in fresh:
            if event.feed_id != target:
                raise ValueError(
                    f"EVENT_FEED_WRONG_STREAM: event '{event.event_id}' belongs to "
                    f"'{event.feed_id}', not '{target}'"
                )
            self._buffer.append(event)
            for sub in self._subscribers:
                if event.sequence <= sub.cursor:
                    continue
                if len(sub.queue) >= self._max_queue:
                    sub.queue.popleft()
                    sub.gap = SubscriberGapError(
                        target,
                        resume_sequence=sub.queue[-1].sequence if sub.queue else sub.cursor,
                        dropped=sub.gap.dropped + 1 if sub.gap else 1,
                    )
                sub.queue.append(event)
        self._polled_once = True
        return fresh

    def subscribe(
        self, namespace: str, after_sequence: int = 0
    ) -> Iterator[CanonicalMarketEvent]:
        """Replay buffered events above ``after_sequence``, then stream live ones.

        Replay is delivered directly (never queued); only events arriving via
        later polls use the bounded live queue, where overflow raises an
        explicit gap instead of silently skipping.
        """
        if not self._polled_once:
            self.poll(self._feed_id)
        sub = _Subscriber(namespace=namespace, cursor=after_sequence)
        self._subscribers.append(sub)
        try:
            for event in self._buffer:
                if event.sequence > after_sequence:
                    yield event
                    sub.cursor = event.sequence
            while True:
                if sub.gap is not None:
                    gap, sub.gap = sub.gap, None
                    raise gap
                if not sub.queue:
                    return
                event = sub.queue.popleft()
                sub.cursor = event.sequence
                yield event
        finally:
            if sub in self._subscribers:
                self._subscribers.remove(sub)


__all__ = [
    "EventFeed",
    "SubscriberGapError",
    "UpstreamSource",
]
