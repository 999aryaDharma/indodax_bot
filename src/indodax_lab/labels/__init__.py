"""Public exports for the labels domain (LABEL-01..LABEL-02)."""

from .returns import (
    NetReturnConfig,
    NetReturnLabel,
    build_net_return_label,
    build_net_return_labels_frame,
)

__all__ = [
    "NetReturnConfig",
    "NetReturnLabel",
    "build_net_return_label",
    "build_net_return_labels_frame",
]
