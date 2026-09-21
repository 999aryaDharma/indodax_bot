"""Base strategy contracts, specifications, and decision frames (STRAT-01)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from typing import Any, Callable, Sequence
import pandas as pd
from pydantic import BaseModel, ConfigDict, field_validator

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def _compute_logic_hash(func: Callable) -> str:
    """Deterministic hash of callable code structure to detect logic changes."""
    try:
        code = getattr(func, "__code__", None)
        if code is not None:
            raw = f"{code.co_code}:{code.co_consts}:{code.co_names}"
        else:
            raw = str(func)
    except Exception:
        raw = str(func)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class StrategySpecification(BaseModel):
    """Declarative specification of a strategy candidate in the research lab catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: str
    version: str
    family: str
    universe_tier: str = "top_liquid"
    timeframes: list[str]
    signal_timing: str = "bar_close"
    execution_timing: str = "next_bar_open"
    parameters: dict[str, Any]
    risk_profile: dict[str, Any]
    split: str
    status: str = "active"
    description: str | None = None

    def parameters_hash(self) -> str:
        """Deterministic SHA256 digest of strategy parameters."""
        raw = json.dumps(self.parameters, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DecisionFrame:
    """Causal, point-in-time decision frame presenting closed features at as_of."""

    def __init__(
        self,
        as_of: datetime,
        features: pd.DataFrame,
        eligible_pairs: Sequence[str],
        universe_snapshot_id: str | None = None,
        feature_set_id: str | None = None,
        feature_set_version: str | None = None,
    ) -> None:
        self.as_of = _ensure_utc(as_of, "as_of")
        self.universe_snapshot_id = universe_snapshot_id
        self.feature_set_id = feature_set_id
        self.feature_set_version = feature_set_version

        # Invariant checks: No future or ineligible rows are permitted inside DecisionFrame
        if not features.empty:
            if "decision_ts" in features.columns:
                dec_ts = pd.to_datetime(features["decision_ts"], utc=True)
                if (dec_ts > self.as_of).any():
                    raise ValueError("FUTURE_OR_INELIGIBLE_ROWS_FORBIDDEN: decision_ts exceeds as_of")
            if "row_ready_at" in features.columns:
                ready_ts = pd.to_datetime(features["row_ready_at"], utc=True)
                if (ready_ts > self.as_of).any():
                    raise ValueError("FUTURE_OR_INELIGIBLE_ROWS_FORBIDDEN: row_ready_at exceeds as_of")
            if "eligible" in features.columns:
                if not (features["eligible"] == True).all():
                    raise ValueError("FUTURE_OR_INELIGIBLE_ROWS_FORBIDDEN: contains ineligible rows")

        self.features = features.copy(deep=True)
        self.eligible_pairs = tuple(sorted(list(eligible_pairs)))

    def get_pair_features(self, pair: str) -> pd.DataFrame:
        """Return feature rows for an eligible pair up to as_of, sorted chronologically."""
        if pair not in self.eligible_pairs:
            return pd.DataFrame()
        p_df = self.features[self.features["pair"] == pair]
        if "decision_ts" in p_df.columns:
            return p_df.sort_values("decision_ts").copy()
        return p_df.copy()

    def latest_row(self, pair: str) -> pd.Series | None:
        """Return latest available feature row for a pair at or before as_of."""
        p_df = self.get_pair_features(pair)
        if p_df.empty:
            return None
        return p_df.iloc[-1]


def create_decision_frame(
    features: pd.DataFrame,
    as_of: datetime,
    universe_snapshot_id: str | None = None,
    feature_set_id: str | None = None,
    feature_set_version: str | None = None,
) -> DecisionFrame:
    """Construct a DecisionFrame, strictly filtering out future and ineligible rows."""
    utc_as_of = _ensure_utc(as_of, "as_of")

    if features.empty:
        return DecisionFrame(
            as_of=utc_as_of,
            features=features.copy(),
            eligible_pairs=(),
            universe_snapshot_id=universe_snapshot_id,
            feature_set_id=feature_set_id,
            feature_set_version=feature_set_version,
        )

    df = features.copy()

    # Exclude future decision timestamps
    if "decision_ts" in df.columns:
        df = df[pd.to_datetime(df["decision_ts"], utc=True) <= utc_as_of]

    # Exclude future availability
    if "row_ready_at" in df.columns:
        df = df[pd.to_datetime(df["row_ready_at"], utc=True) <= utc_as_of]

    # Exclude ineligible rows (missing data, warmup in progress)
    if "eligible" in df.columns:
        df = df[df["eligible"] == True]

    eligible_pairs = sorted(df["pair"].unique().tolist()) if "pair" in df.columns and not df.empty else []

    return DecisionFrame(
        as_of=utc_as_of,
        features=df,
        eligible_pairs=eligible_pairs,
        universe_snapshot_id=universe_snapshot_id,
        feature_set_id=feature_set_id,
        feature_set_version=feature_set_version,
    )


class RegisteredStrategy:
    """Registered strategy instance bound to a validated specification and stateless decision function.

    Guarantees:
    - Strategies only produce order intents (SignalIntent).
    - Strategies have zero fill or ledger authority.
    """

    def __init__(
        self,
        specification: StrategySpecification,
        decide_fn: Callable[[DecisionFrame], list[SignalIntent]],
    ) -> None:
        self.specification = specification
        self.decide_fn = decide_fn
        self.logic_hash = _compute_logic_hash(decide_fn)

    def decide(self, frame: DecisionFrame) -> list[SignalIntent]:
        """Produce declarative trading signals over causal point-in-time DecisionFrame."""
        if not isinstance(frame, DecisionFrame):
            raise TypeError(f"EXPECTED_DECISION_FRAME_GOT:{type(frame).__name__}")

        raw_intents = self.decide_fn(frame)

        if not isinstance(raw_intents, list):
            raise TypeError("ONLY_SIGNAL_INTENT_ALLOWED: decide function must return a list")

        validated_intents: list[SignalIntent] = []
        for item in raw_intents:
            if not isinstance(item, SignalIntent):
                raise TypeError(
                    f"ONLY_SIGNAL_INTENT_ALLOWED: expected SignalIntent, got {type(item).__name__}"
                )
            # Long-only spot trading check: side must be BUY or SELL, desired_qty > 0
            if item.side not in (OrderSide.BUY, OrderSide.SELL):
                raise ValueError(f"UNSUPPORTED_ORDER_SIDE:{item.side}")
            if item.desired_qty <= Decimal("0"):
                raise ValueError(f"POSITIVE_DESIRED_QTY_REQUIRED:{item.desired_qty}")

            validated_intents.append(item)

        return validated_intents
