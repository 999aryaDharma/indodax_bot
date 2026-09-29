"""Research runtime composition with a transitive live-writer boundary (RP-04).

``build_research_runtime`` wires a ``RuntimeKernel`` from simulated adapters
only. Any live execution writer — the concrete Indodax client, a subclass, or
a factory/wrapper resolving to one — is refused before the kernel exists.

Guarantees (CONTRACTS.md):
- Research process/package import boundary rejects write-adapter
  reachability, including factories and wrapper injection.
- The kernel it returns can never resolve a live adapter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from indodax_lab.execution.shadow_venue import ShadowVenueAdapter
from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter
from indodax_lab.execution.venue import TradingVenue
from indodax_lab.runtime.kernel import RuntimeKernel

_LIVE_WRITER_MARKERS = ("indodaxtradingclient", "indodaxtradingvenue")
_LIVE_MODULE_MARKER = "indodax_lab.execution.indodax_trading"


class ResearchBoundaryError(Exception):
    """A live execution writer was offered to the research composition."""


def _is_live_writer(venue: Any, _depth: int = 0) -> bool:
    """Detect live writers transitively: exact class, subclass, or wrapper.

    A wrapper subclass inherits the live MRO, so checking every class in the
    method-resolution order (by qualified name and defining module) catches
    factory/wrapper injection, not just the concrete client. A composition
    wrapper *holding* a live client is caught by walking one level of
    instance attributes; deeper nesting is out of scope and documented.
    """
    for klass in type(venue).__mro__:
        name = f"{klass.__module__}.{klass.__qualname__}".lower()
        if klass.__name__.lower() in _LIVE_WRITER_MARKERS:
            return True
        if _LIVE_MODULE_MARKER in klass.__module__.lower() and "readonly" not in name:
            return True
    if _depth >= 1:
        return False
    try:
        held = list(vars(venue).values())
    except TypeError:
        return False
    return any(_is_live_writer(value, _depth + 1) for value in held)


def _resolve_venue(spec: Mapping[str, Any]) -> tuple[TradingVenue, str]:
    """Resolve the venue spec to a simulated adapter or refuse a live writer."""
    if "venue_factory" in spec:
        factory = spec["venue_factory"]
        if not callable(factory):
            raise ResearchBoundaryError(
                "LIVE_WRITER_FORBIDDEN: venue_factory is not callable"
            )
        return _resolve_venue({"venue": factory()})
    venue = spec.get("venue", "simulator")
    if isinstance(venue, str):
        if venue == "simulator":
            return SimulatorVenueAdapter(), "simulator"
        if venue == "shadow":
            return ShadowVenueAdapter(), "shadow"
        raise ResearchBoundaryError(
            f"LIVE_WRITER_FORBIDDEN: unknown venue name {venue!r}; research "
            "composition only resolves 'simulator' or 'shadow'"
        )
    if _is_live_writer(venue):
        raise ResearchBoundaryError(
            f"LIVE_WRITER_FORBIDDEN: {type(venue).__name__} resolves to a live "
            "execution writer; research runtime cannot hold one"
        )
    if not isinstance(venue, TradingVenue):
        raise ResearchBoundaryError(
            f"LIVE_WRITER_FORBIDDEN: {type(venue).__name__} does not implement "
            "the TradingVenue protocol"
        )
    return venue, type(venue).__name__


def build_research_runtime(
    spec: Mapping[str, Any],
    *,
    kernel_factory: Callable[..., RuntimeKernel] | None = None,
) -> RuntimeKernel:
    """Compose a research ``RuntimeKernel`` from simulated adapters only.

    ``spec`` carries ``venue`` (``'simulator'`` | ``'shadow'`` | a
    ``TradingVenue`` instance) or ``venue_factory`` (resolved then vetted),
    plus kernel wiring passed through to ``kernel_factory``.

    Scope note: a caller-supplied ``kernel_factory`` receives the vetted
    venue but may ignore it, so the no-live-adapter guarantee holds for the
    default factory; custom factories are an explicit test seam.
    """
    venue, venue_name = _resolve_venue(spec)
    factory = kernel_factory or RuntimeKernel.minimal
    return factory(venue=venue, venue_name=venue_name)


__all__ = [
    "ResearchBoundaryError",
    "build_research_runtime",
]
