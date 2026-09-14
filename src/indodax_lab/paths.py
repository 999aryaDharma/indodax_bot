"""Explicit runtime locations for research data and artifacts."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LabPaths:
    """Roots owned by a lab runtime, resolved without using the process CWD."""

    data_root: Path
    artifact_root: Path

    @classmethod
    def from_env(cls, project_root: Path) -> "LabPaths":
        """Build runtime roots from an explicit project root and output overrides."""
        return cls(
            data_root=Path(os.getenv("INDODAX_LAB_DATA_DIR", project_root / "lab-data")),
            artifact_root=Path(
                os.getenv("INDODAX_LAB_ARTIFACT_DIR", project_root / "lab-artifacts")
            ),
        )
