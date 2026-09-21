"""In-memory thread-safe metrics collector for trading telemetry."""

from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from typing import Any


class MetricsCollector:
    """Institutional runtime metrics registry collecting counters, gauges, and latencies."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, list[float]] = {}

    def _format_key(self, name: str, labels: Mapping[str, str] | None = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> float:
        """Increment a monotonic counter."""
        key = self._format_key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + float(value)
            return self._counters[key]

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        """Set a point-in-time gauge value."""
        key = self._format_key(name, labels)
        with self._lock:
            self._gauges[key] = float(value)

    def record_timing(
        self,
        name: str,
        duration_ms: float,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        """Record an execution latency sample in milliseconds."""
        key = self._format_key(name, labels)
        with self._lock:
            if key not in self._timings:
                self._timings[key] = []
            self._timings[key].append(float(duration_ms))

    def export(self) -> dict[str, Any]:
        """Export all current metrics as a structured dictionary."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timings": {
                    k: {
                        "count": len(v),
                        "avg_ms": (sum(v) / len(v)) if v else 0.0,
                        "max_ms": max(v) if v else 0.0,
                    }
                    for k, v in self._timings.items()
                },
            }
