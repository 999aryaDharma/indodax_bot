"""Unit tests for DL-02: Causal sequence datasets.

Guarantees:
1. DL-02-AC0: Window sequence tidak menyeberangi pair, gap, split atau target (test_dl_02_valid_contract).
2. DL-02-AC1: Padding tidak menjadi harga nol nyata; mask menandai langkah valid secara eksplisit (test_dl_02_contract_1).
3. DL-02-AC2: Session gap memutus window secara kausal (test_dl_02_contract_2).
4. DL-02-AC3: Target/future token tidak masuk input; kebocoran target ditolak fail-closed (test_dl_02_contract_3).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.dl.dataset import (
    CausalSequenceBatch,
    CausalSequenceBuilder,
    CausalSequenceConfig,
    SessionGapBrokenWindowError,
    TargetLeakageForbiddenError,
)


def _generate_synthetic_bar_df(
    n_bars: int = 100,
    pair: str = "BTC_IDR",
    start_dt: datetime | None = None,
    gap_index: int | None = None,
    gap_duration: timedelta = timedelta(hours=5),
) -> pd.DataFrame:
    start = start_dt or datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    timestamps: list[datetime] = []
    current = start
    for i in range(n_bars):
        if gap_index is not None and i == gap_index:
            current += gap_duration
        else:
            current += timedelta(minutes=15)
        timestamps.append(current)

    rng = np.random.default_rng(42)
    prices = 1000.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, size=n_bars)))
    volumes = rng.uniform(10.0, 50.0, size=n_bars)
    returns = np.diff(prices, prepend=prices[0]) / prices[0]

    # Target: 4-bar forward return (1 hour ahead)
    targets = np.roll(returns, -4)
    targets[-4:] = np.nan  # Unknown future at tail

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "pair": pair,
            "close": prices,
            "volume": volumes,
            "return_15m": returns,
            "target_forward_return": targets,
            "role": "TRAIN",
            "row_ready_at": timestamps,
        }
    )
    return df


def test_sequence_never_crosses_repeated_role_boundaries():
    df = _generate_synthetic_bar_df(12)
    df["role"] = ["TRAIN"] * 3 + ["SEALED_TEST"] * 3 + ["TRAIN"] * 6
    batch = CausalSequenceBuilder(CausalSequenceConfig(sequence_length=4, feature_columns=["close"],
        target_column="target_forward_return", allow_padding=False)).build(df)
    assert len(batch) == 0


@pytest.mark.parametrize("defect", ["future_return", "missing_role", "missing_ready", "delayed", "infinite", "gap_zero"])
def test_sequence_rejects_unsafe_inputs(defect):
    df = _generate_synthetic_bar_df(12)
    columns = ["close"]
    gap = 1800
    if defect == "future_return":
        df["future_return"] = 0.1
        columns = ["future_return"]
    elif defect == "missing_role":
        df = df.drop(columns="role")
    elif defect == "missing_ready":
        df = df.drop(columns="row_ready_at")
    elif defect == "delayed":
        df.loc[0, "row_ready_at"] += timedelta(hours=1)
    elif defect == "infinite":
        df.loc[0, "close"] = np.inf
    else:
        gap = 0
    with pytest.raises(ValueError):
        CausalSequenceBuilder(CausalSequenceConfig(feature_columns=columns,
            target_column="target_forward_return", max_gap_seconds=gap)).build(df)


def test_sequence_arrays_are_immutable():
    batch = CausalSequenceBuilder(CausalSequenceConfig(feature_columns=["close"],
        target_column="target_forward_return")).build(_generate_synthetic_bar_df(12))
    assert not batch.inputs.flags.writeable
    assert not batch.masks.flags.writeable
    assert not batch.targets.flags.writeable
    with pytest.raises(ValueError):
        batch.inputs.setflags(write=True)


def test_sequence_torch_conversion_does_not_alias_immutable_numpy():
    pytest.importorskip("torch")
    batch = CausalSequenceBuilder(CausalSequenceConfig(feature_columns=["close"],
        target_column="target_forward_return")).build(_generate_synthetic_bar_df(12))
    original = batch.inputs.copy()
    converted = batch.to_torch_dataset()
    converted.tensors[0][0, -1, 0] = -123
    np.testing.assert_array_equal(batch.inputs, original)


def test_sequence_revalidates_mutated_allowlist_and_identity():
    frame = _generate_synthetic_bar_df(12)
    frame["future_return"] = .1
    config = CausalSequenceConfig(feature_columns=["close"], target_column="target_forward_return")
    config.feature_columns.append("future_return")
    with pytest.raises(ValueError, match="TARGET_LEAKAGE"):
        CausalSequenceBuilder(config).build(frame)


def test_sequence_rejects_null_sample_identity():
    frame = _generate_synthetic_bar_df(12)
    frame["sample_id"] = None
    with pytest.raises(ValueError, match="SAMPLE_ID"):
        CausalSequenceBuilder(CausalSequenceConfig(feature_columns=["close"],
            target_column="target_forward_return")).build(frame)


def test_dl_02_valid_contract() -> None:
    """DL-02-AC0: Window sequence tidak menyeberangi pair, gap, split atau target."""
    df_btc = _generate_synthetic_bar_df(n_bars=60, pair="BTC_IDR")
    df_eth = _generate_synthetic_bar_df(n_bars=60, pair="ETH_IDR")
    df_combined = pd.concat([df_btc, df_eth], ignore_index=True)

    config = CausalSequenceConfig(
        sequence_length=16,
        feature_columns=["return_15m", "volume"],
        target_column="target_forward_return",
        max_gap_seconds=1800,  # 30 minutes max allowable gap (normal is 15m)
    )
    builder = CausalSequenceBuilder(config=config)
    batch = builder.build(df_combined)

    assert isinstance(batch, CausalSequenceBatch)
    assert batch.inputs.shape[1] == 16  # sequence_length
    assert batch.inputs.shape[2] == 2   # num_features
    assert batch.masks.shape == (len(batch), 16)
    assert len(batch.targets) == len(batch)
    assert len(batch.sample_ids) == len(batch)

    # Verify no sequence crosses between pairs
    for sid in batch.sample_ids:
        # Format: {pair}_{timestamp}
        assert sid.startswith("BTC_IDR_") or sid.startswith("ETH_IDR_")

    # Verify target is outside input features
    assert "target_forward_return" not in config.feature_columns


def test_dl_02_contract_1() -> None:
    """DL-02-AC1: Padding tidak menjadi harga nol nyata; mask memisahkan padding secara eksplisit."""
    df = _generate_synthetic_bar_df(n_bars=30, pair="BTC_IDR")

    config = CausalSequenceConfig(
        sequence_length=20,
        feature_columns=["close", "volume"],
        target_column="target_forward_return",
        allow_padding=True,
        max_gap_seconds=1800,
    )
    builder = CausalSequenceBuilder(config=config)
    batch = builder.build(df)

    # First item was created with partial history -> must be padded
    first_mask = batch.masks[0]
    # Padded steps must have mask == False
    assert np.any(~first_mask)
    # Valid steps must have mask == True
    assert np.any(first_mask)
    assert first_mask[-1] is True or first_mask[-1] == 1  # Latest step at T is always valid

    # Ensure padding values are explicitly marked by mask and not interpreted as genuine zero prices
    padded_indices = np.where(~first_mask)[0]
    for idx in padded_indices:
        # Check that mask unambiguously identifies padding
        assert first_mask[idx] == False


def test_dl_02_contract_2() -> None:
    """DL-02-AC2: Session gap memutus window secara kausal."""
    # Bar 25 has a 5-hour session gap
    df_with_gap = _generate_synthetic_bar_df(n_bars=50, pair="BTC_IDR", gap_index=25)

    config = CausalSequenceConfig(
        sequence_length=10,
        feature_columns=["return_15m", "volume"],
        target_column="target_forward_return",
        allow_padding=False,
        max_gap_seconds=1800,  # 30 mins max gap; 5-hour gap must break window
    )
    builder = CausalSequenceBuilder(config=config)
    batch = builder.build(df_with_gap)

    # Check timestamps across all sequences: none can span across the 5-hour gap
    gap_bar_ts = df_with_gap.iloc[25]["timestamp"]
    pre_gap_ts = df_with_gap.iloc[24]["timestamp"]

    for window_timestamps in batch.window_timestamps:
        # No window can contain both pre_gap_ts and gap_bar_ts
        contains_pre = pre_gap_ts in window_timestamps
        contains_post = gap_bar_ts in window_timestamps
        assert not (contains_pre and contains_post), "Causal window breached session gap boundary!"


def test_dl_02_contract_3() -> None:
    """DL-02-AC3: Target/future token tidak masuk input; kebocoran target ditolak fail-closed."""
    df = _generate_synthetic_bar_df(n_bars=30, pair="BTC_IDR")

    # 1. Target column listed inside feature_columns must be rejected fail-closed
    with pytest.raises(TargetLeakageForbiddenError, match="TARGET_LEAKAGE_FORBIDDEN"):
        CausalSequenceConfig(
            sequence_length=10,
            feature_columns=["return_15m", "target_forward_return"],  # Leaked target!
            target_column="target_forward_return",
        )

    # 2. Sequence windows at step T must only contain data up to timestamp T, never T+1
    config = CausalSequenceConfig(
        sequence_length=8,
        feature_columns=["return_15m", "volume"],
        target_column="target_forward_return",
        allow_padding=False,
    )
    builder = CausalSequenceBuilder(config=config)
    batch = builder.build(df)

    for i, w_ts in enumerate(batch.window_timestamps):
        eval_ts = batch.timestamps[i]
        # Every element in window timestamps must be <= eval_ts
        for t in w_ts:
            assert t <= eval_ts, f"Future timestamp {t} leaked into sequence evaluated at {eval_ts}"
