"""Base strategy contracts, specifications, and decision frames (STRAT-01)."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import CodeType
from typing import Any, Callable, Sequence

import pandas as pd
from pydantic import BaseModel, ConfigDict

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def _stable_value(value: Any) -> Any:
    """Canonicalize strategy captures; reject state whose identity cannot be pinned."""
    if isinstance(value, BaseModel):
        return _stable_value(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return _stable_value(value.value)
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, (datetime, date)):
        return {type(value).__name__: value.isoformat()}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, CodeType):
        return _code_identity(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NON_FINITE_STRATEGY_CAPTURE")
        return {"float": value.hex()}
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("NON_STRING_STRATEGY_CAPTURE_KEY")
        return {key: _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_stable_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_stable_value(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    raise ValueError(f"UNSTABLE_STRATEGY_CAPTURE:{type(value).__name__}")


def _code_identity(code: CodeType) -> dict[str, Any]:
    return {
        "bytecode": code.co_code.hex(),
        "constants": [_stable_value(value) for value in code.co_consts],
        "names": code.co_names,
        "varnames": code.co_varnames,
        "argcount": code.co_argcount,
        "kwonlyargcount": code.co_kwonlyargcount,
    }


def _compute_logic_hash(func: Callable) -> str:
    """Hash code, defaults and closure values so captured parameters bind identity."""
    code = getattr(func, "__code__", None)
    if code is None:
        raise ValueError("STRATEGY_CALLABLE_CODE_REQUIRED")
    closure = getattr(func, "__closure__", None) or ()
    cells = []
    for name, cell in zip(code.co_freevars, closure, strict=True):
        try:
            value = cell.cell_contents
        except ValueError as exc:
            raise ValueError("EMPTY_STRATEGY_CLOSURE_CELL") from exc
        cells.append((name, _stable_value(value)))
    payload = {
        "code": _code_identity(code),
        "defaults": _stable_value(func.__defaults__),
        "kwdefaults": _stable_value(func.__kwdefaults__),
        "closure": cells,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
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


def _validate_frame_evidence(features: pd.DataFrame) -> None:
    required = {"pair", "decision_ts", "row_ready_at", "eligible"}
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"DECISION_FRAME_REQUIRED_COLUMNS:{','.join(sorted(missing))}")
    for column in ("decision_ts", "row_ready_at"):
        parsed = pd.to_datetime(features[column], utc=True, errors="coerce")
        if parsed.isna().any():
            raise ValueError(f"INVALID_CAUSAL_TIMESTAMP:{column}")
    if features["eligible"].isna().any() or not features["eligible"].isin([True, False]).all():
        raise ValueError("INVALID_ELIGIBILITY_EVIDENCE")
    if features["pair"].isna().any() or features["pair"].astype(str).str.len().eq(0).any():
        raise ValueError("INVALID_PAIR_EVIDENCE")


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

        # Invariant checks: causal evidence is mandatory for every nonempty frame.
        if not features.empty:
            _validate_frame_evidence(features)
            dec_ts = pd.to_datetime(features["decision_ts"], utc=True, errors="coerce")
            ready_ts = pd.to_datetime(features["row_ready_at"], utc=True, errors="coerce")
            if (dec_ts > self.as_of).any():
                raise ValueError("FUTURE_OR_INELIGIBLE_ROWS_FORBIDDEN: decision_ts exceeds as_of")
            if (ready_ts > self.as_of).any():
                raise ValueError("FUTURE_OR_INELIGIBLE_ROWS_FORBIDDEN: row_ready_at exceeds as_of")
            if not features["eligible"].all():
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
    _validate_frame_evidence(df)

    # Exclude future decision timestamps
    decision_ts = pd.to_datetime(df["decision_ts"], utc=True, errors="coerce")
    row_ready_at = pd.to_datetime(df["row_ready_at"], utc=True, errors="coerce")
    df = df.loc[
        decision_ts.le(utc_as_of) & row_ready_at.le(utc_as_of) & df["eligible"].eq(True)
    ]

    eligible_pairs = (
        sorted(df["pair"].unique().tolist())
        if "pair" in df.columns and not df.empty
        else []
    )

    return DecisionFrame(
        as_of=utc_as_of,
        features=df,
        eligible_pairs=eligible_pairs,
        universe_snapshot_id=universe_snapshot_id,
        feature_set_id=feature_set_id,
        feature_set_version=feature_set_version,
    )


class RegisteredStrategy:
    """Registered strategy instance bound to a validated spec and stateless function.

    Guarantees:
    - Strategies only produce order intents (SignalIntent).
    - Strategies have zero fill or ledger authority.
    """

    __slots__ = ("_specification", "_decide_fn", "_logic_hash")

    def __init__(
        self,
        specification: StrategySpecification,
        decide_fn: Callable[[DecisionFrame], list[SignalIntent]],
    ) -> None:
        object.__setattr__(self, "_specification", specification.model_copy(deep=True))
        object.__setattr__(self, "_decide_fn", decide_fn)
        object.__setattr__(self, "_logic_hash", _compute_logic_hash(decide_fn))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("REGISTERED_STRATEGY_IMMUTABLE")

    @property
    def specification(self) -> StrategySpecification:
        """Return a defensive copy so nested config edits cannot change registration."""
        return self._specification.model_copy(deep=True)

    @property
    def logic_hash(self) -> str:
        return self._logic_hash

    def decide(self, frame: DecisionFrame) -> list[SignalIntent]:
        """Produce declarative trading signals over causal point-in-time DecisionFrame."""
        if not isinstance(frame, DecisionFrame):
            raise TypeError(f"EXPECTED_DECISION_FRAME_GOT:{type(frame).__name__}")

        if _compute_logic_hash(self._decide_fn) != self._logic_hash:
            raise ValueError("REGISTERED_STRATEGY_LOGIC_MUTATED")
        raw_intents = self._decide_fn(frame)

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
