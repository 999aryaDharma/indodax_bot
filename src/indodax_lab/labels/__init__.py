"""Public exports for the labels domain (LABEL-01..LABEL-02, SPLIT-01, TRAIN-01)."""

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
from .splits import (
    ExposedPeriodViolationError,
    FoldAssignment,
    FoldWindow,
    SampleRecord,
    SampleRole,
    SplitManifest,
    SplitPolicy,
    assign_folds,
)
from .materializer import (
    ArtifactIntegrityError,
    AvailabilityMismatchError,
    DuplicateSampleError,
    TargetLeakageError,
    TrainingDatasetArtifact,
    TrainingDatasetManifest,
    materialize_training_dataset,
)

__all__ = [
    "ArtifactIntegrityError",
    "AvailabilityMismatchError",
    "BarrierTouch",
    "DuplicateSampleError",
    "ExposedPeriodViolationError",
    "FoldAssignment",
    "FoldWindow",
    "NetReturnConfig",
    "NetReturnLabel",
    "SampleRecord",
    "SampleRole",
    "SplitManifest",
    "SplitPolicy",
    "TargetLeakageError",
    "TrainingDatasetArtifact",
    "TrainingDatasetManifest",
    "TripleBarrierConfig",
    "TripleBarrierLabel",
    "assign_folds",
    "build_net_return_label",
    "build_net_return_labels_frame",
    "build_triple_barrier_label",
    "compute_concurrency_weights",
    "materialize_training_dataset",
]
