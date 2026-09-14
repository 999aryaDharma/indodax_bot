"""Public exports for the labels domain (LABEL-01..LABEL-02)."""

from .returns import (
    NetReturnConfig,
    NetReturnLabel,
    build_net_return_label,
    build_net_return_labels_frame,
)
from .triple_barrier import (
    BarrierTouch,
    TripleBarrierConfig,
    TripleBarrierLabel,
    build_triple_barrier_label,
    compute_concurrency_weights,
)

__all__ = [
    "NetReturnConfig",
    "NetReturnLabel",
    "build_net_return_label",
    "build_net_return_labels_frame",
    "BarrierTouch",
    "TripleBarrierConfig",
    "TripleBarrierLabel",
    "build_triple_barrier_label",
    "compute_concurrency_weights",
]
