"""Typed declarative pipeline composer (RW2-03).

One validated graph for TA-only and hybrid (TA+ML+DL soft-vote) compositions.
``PipelineService`` owns draft/revision/publish lifecycle; validation and the
YAML presentation contract live in :mod:`indodax_lab.pipelines.validation`.
"""

from indodax_lab.pipelines.registry import PipelineService
from indodax_lab.pipelines.validation import (
    PipelineValidationError,
    ValidationIssue,
    ValidationReport,
    canonicalize,
)

__all__ = [
    "PipelineService",
    "PipelineValidationError",
    "ValidationIssue",
    "ValidationReport",
    "canonicalize",
]
