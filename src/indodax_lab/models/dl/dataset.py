"""Causal sequence dataset builder and batch containers for neural time-series (DL-02).

Guarantees:
1. DL-02-AC0: Window sequences never cross pair boundaries, session gaps, or split targets.
2. DL-02-AC1: Pre-padding steps are explicitly marked with boolean masks; never treated as genuine market prices.
3. DL-02-AC2: Session gaps strictly break sequence windows to prevent temporal discontinuity leakage.
4. DL-02-AC3: Targets and future tokens are strictly excluded from input tensors fail-closed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.models.dl.checkpoint import check_torch_availability, require_torch


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TargetLeakageForbiddenError(ValueError):
    """Raised when the target column is included in the input feature columns."""


class SessionGapBrokenWindowError(ValueError):
    """Raised when a sequence window breaches a session gap."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class CausalSequenceConfig(BaseModel):
    """Configuration for causal sequence extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    sequence_length: int = 30
    feature_columns: list[str]
    target_column: str
    pair_column: str = "pair"
    timestamp_column: str = "timestamp"
    max_gap_seconds: int = 1800  # Default 30 minutes
    allow_padding: bool = True
    padding_value: float = 0.0

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.sequence_length <= 0:
            raise ValueError(f"POSITIVE_SEQUENCE_LENGTH_REQUIRED: Got {self.sequence_length}")
        if self.max_gap_seconds <= 0 or not np.isfinite(self.padding_value):
            raise ValueError("POSITIVE_GAP_FINITE_PADDING_REQUIRED")
        if not self.feature_columns or len(set(self.feature_columns)) != len(self.feature_columns):
            raise ValueError("UNIQUE_FEATURE_ALLOWLIST_REQUIRED")
        if any(c == self.target_column or c.lower().startswith(("future_", "label_", "target_", "outcome_", "exit_", "entry_", "net_return", "binary_label")) for c in self.feature_columns):
            raise TargetLeakageForbiddenError(
                f"TARGET_LEAKAGE_FORBIDDEN: Target '{self.target_column}' cannot be part of feature columns"
            )


# ---------------------------------------------------------------------------
# Batch Container
# ---------------------------------------------------------------------------


class CausalSequenceBatch:
    """Immutable batch of causal sequence windows with explicit masks and metadata."""

    def __init__(
        self,
        inputs: np.ndarray,
        masks: np.ndarray,
        targets: np.ndarray,
        sample_ids: list[str],
        timestamps: list[datetime],
        window_timestamps: list[list[datetime]],
        feature_names: list[str],
    ) -> None:
        self.inputs = np.frombuffer(inputs.tobytes(), dtype=inputs.dtype).reshape(inputs.shape)
        self.masks = np.frombuffer(masks.tobytes(), dtype=masks.dtype).reshape(masks.shape)
        self.targets = np.frombuffer(targets.tobytes(), dtype=targets.dtype).reshape(targets.shape)
        self.sample_ids = sample_ids
        self.timestamps = timestamps
        self.window_timestamps = window_timestamps
        self.feature_names = feature_names

    def __len__(self) -> int:
        return len(self.sample_ids)

    def to_torch_dataset(self) -> Any:
        """Convert batch to PyTorch TensorDataset if torch is available."""
        torch = require_torch()
        in_t = torch.tensor(self.inputs, dtype=torch.float32)
        mask_t = torch.tensor(self.masks, dtype=torch.bool)
        tgt_t = torch.tensor(self.targets, dtype=torch.float32).unsqueeze(1)
        return torch.utils.data.TensorDataset(in_t, mask_t, tgt_t)


# ---------------------------------------------------------------------------
# Sequence Builder
# ---------------------------------------------------------------------------


class CausalSequenceBuilder:
    """Builds strictly causal, gap-aware sequence windows grouped by asset pair."""

    def __init__(self, config: CausalSequenceConfig) -> None:
        self.config = config

    def build(self, df: pd.DataFrame) -> CausalSequenceBatch:
        """Extract sequence windows respecting pair boundaries and temporal continuity."""
        # Frozen models may still contain caller-mutated lists; validate at use.
        CausalSequenceConfig(**self.config.model_dump())
        required = [self.config.pair_column, self.config.timestamp_column, "role", "row_ready_at", self.config.target_column, *self.config.feature_columns]
        if not df.columns.is_unique or not set(required).issubset(df.columns):
            raise ValueError("SEQUENCE_ROLE_READINESS_FEATURES_REQUIRED")
        df = df.copy()
        if "sample_id" in df and (not df["sample_id"].map(lambda v: isinstance(v, str) and bool(v.strip())).all() or df["sample_id"].duplicated().any()):
            raise ValueError("SEQUENCE_SAMPLE_ID_INVALID")
        for column in (self.config.timestamp_column, "row_ready_at"):
            for value in df[column]:
                ts = pd.Timestamp(value)
                if pd.isna(ts) or ts.tzinfo is None or ts.utcoffset().total_seconds() != 0:
                    raise ValueError("SEQUENCE_UTC_REQUIRED")
            df[column] = pd.to_datetime(df[column], utc=True)
        if df[self.config.pair_column].isna().any() or not df["role"].isin(["TRAIN", "VALIDATION", "CALIBRATION", "SEALED_TEST", "PURGED", "EMBARGOED", "EXCLUDED"]).all():
            raise ValueError("SEQUENCE_IDENTITY_ROLE_INVALID")
        if (df["row_ready_at"] > df[self.config.timestamp_column]).any():
            raise ValueError("SEQUENCE_FEATURE_NOT_READY")
        if not np.isfinite(df[self.config.feature_columns].to_numpy(dtype=float)).all():
            raise ValueError("SEQUENCE_NONFINITE_FEATURE")
        if "eligible" in df and not df["eligible"].eq(True).all():
            raise ValueError("SEQUENCE_INELIGIBLE_FEATURE")
        all_inputs: list[np.ndarray] = []
        all_masks: list[np.ndarray] = []
        all_targets: list[float] = []
        all_sample_ids: list[str] = []
        all_timestamps: list[datetime] = []
        all_window_timestamps: list[list[datetime]] = []

        seq_len = self.config.sequence_length
        n_features = len(self.config.feature_columns)

        # Process each asset pair independently
        pairs = df[self.config.pair_column].unique()
        for pair in pairs:
            pair_df = df[df[self.config.pair_column] == pair].sort_values(
                by=self.config.timestamp_column, ascending=True
            ).reset_index(drop=True)

            if len(pair_df) == 0:
                continue

            # Identify contiguous runs broken by session gaps
            ts_series = pd.to_datetime(pair_df[self.config.timestamp_column])
            time_diffs = ts_series.diff().dt.total_seconds()

            # A new segment starts at row 0 or when gap > max_gap_seconds
            if (time_diffs.dropna() <= 0).any():
                raise ValueError("SEQUENCE_STRICT_CHRONOLOGY_REQUIRED")
            breaks = time_diffs > self.config.max_gap_seconds
            for column in ("role", "session_id", "fold_id", "fold_start_ts", "fold_end_ts"):
                if column in pair_df:
                    breaks |= pair_df[column].ne(pair_df[column].shift())
            segment_ids = breaks.cumsum()

            for seg_id, seg_df in pair_df.groupby(segment_ids):
                if seg_df.iloc[0]["role"] in {"PURGED", "EMBARGOED", "EXCLUDED"}:
                    continue
                seg_df = seg_df.reset_index(drop=True)
                seg_len = len(seg_df)

                feature_matrix = seg_df[self.config.feature_columns].values.astype(float)
                target_series = seg_df[self.config.target_column].values.astype(float)
                seg_ts = seg_df[self.config.timestamp_column].tolist()

                for t in range(seg_len):
                    # If target at step t is missing/nan (e.g. unknown forward return at tail), skip
                    tgt_val = target_series[t]
                    if not np.isfinite(tgt_val):
                        continue

                    available_steps = t + 1
                    eval_ts = seg_ts[t]
                    sample_id = seg_df.iloc[t]["sample_id"] if "sample_id" in seg_df else f"{pair}_{eval_ts.isoformat()}"

                    if available_steps >= seq_len:
                        # Full window without padding
                        start_idx = t - seq_len + 1
                        window_features = feature_matrix[start_idx : t + 1]
                        window_mask = np.ones(seq_len, dtype=bool)
                        window_ts = seg_ts[start_idx : t + 1]
                    elif self.config.allow_padding:
                        # Pre-pad with padding_value; mask == False for padding
                        pad_len = seq_len - available_steps
                        pad_features = np.full((pad_len, n_features), self.config.padding_value, dtype=float)
                        valid_features = feature_matrix[0 : t + 1]
                        window_features = np.vstack([pad_features, valid_features])

                        pad_mask = np.zeros(pad_len, dtype=bool)
                        valid_mask = np.ones(available_steps, dtype=bool)
                        window_mask = np.concatenate([pad_mask, valid_mask])

                        # Padded steps have no physical timestamps; record valid ones
                        window_ts = seg_ts[0 : t + 1]
                    else:
                        # Non-padded mode ignores incomplete history
                        continue

                    all_inputs.append(window_features)
                    all_masks.append(window_mask)
                    all_targets.append(tgt_val)
                    all_sample_ids.append(sample_id)
                    all_timestamps.append(eval_ts)
                    all_window_timestamps.append(window_ts)

        if len(all_inputs) == 0:
            inputs_arr = np.empty((0, seq_len, n_features), dtype=float)
            masks_arr = np.empty((0, seq_len), dtype=bool)
            targets_arr = np.empty((0,), dtype=float)
        else:
            inputs_arr = np.stack(all_inputs, axis=0)
            masks_arr = np.stack(all_masks, axis=0)
            targets_arr = np.array(all_targets, dtype=float)

        return CausalSequenceBatch(
            inputs=inputs_arr,
            masks=masks_arr,
            targets=targets_arr,
            sample_ids=all_sample_ids,
            timestamps=all_timestamps,
            window_timestamps=all_window_timestamps,
            feature_names=self.config.feature_columns,
        )
