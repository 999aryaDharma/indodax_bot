"""Cost-aware execution mapper translating calibrated forecasts to order intents (ML-02).

Guarantees:
1. ML-02-AC0: Calibrated forecasts convert to order intent ONLY when net edge strictly exceeds safety margin.
2. ML-02-AC3: Gross and net equivalent forecasts produce identical execution decisions and edge.
3. ADR-002: Costs applied exactly once; NET_RETURN compares directly, GROSS_RETURN subtracts round-trip cost once,
   and PROBABILITY calculates gross expectation before subtracting round-trip cost once.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.contracts.decision import SignalIntent


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class ForecastKind(StrEnum):
    """Semantic target basis of the model forecast (ADR-002)."""

    NET_RETURN = "net_return"
    GROSS_RETURN = "gross_return"
    PROBABILITY = "probability"


class DecisionAction(StrEnum):
    """Decision output of the execution mapper."""

    INTENT = "intent"
    ABSTAIN = "abstain"


class PayoffStructure(BaseModel):
    """Expected win and loss payoffs for mapping probability forecasts to returns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    win_return: float
    loss_return: float

    @model_validator(mode="after")
    def validate_payoffs(self) -> PayoffStructure:
        if self.win_return <= 0.0:
            raise ValueError("WIN_RETURN_MUST_BE_POSITIVE")
        if self.loss_return >= 0.0:
            raise ValueError("LOSS_RETURN_MUST_BE_NEGATIVE")
        return self


class CostBasis(BaseModel):
    """Estimated transaction costs and required safety margin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    estimated_round_trip_cost: float
    safety_margin: float

    @field_validator("estimated_round_trip_cost", "safety_margin")
    @classmethod
    def validate_non_negative(cls, v: float, info) -> float:
        if v < 0.0:
            raise ValueError(f"NON_NEGATIVE_VALUE_REQUIRED:{info.field_name}")
        return v


class ForecastPayload(BaseModel):
    """Model forecast input submitted to the execution mapper."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ForecastKind
    value: float
    pair: str
    decision_ts: datetime
    desired_qty: Decimal
    payoff: PayoffStructure | None = None
    limit_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    role_preference: OrderRole = OrderRole.TAKER
    strategy_id: str = "ml_forecast"
    side: OrderSide = OrderSide.BUY

    @field_validator("decision_ts", mode="after")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v, "decision_ts")

    @field_validator("desired_qty", mode="before")
    @classmethod
    def parse_qty(cls, v: Any) -> Decimal:
        dec = Decimal(str(v))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_DESIRED_QTY_REQUIRED")
        return dec

    @field_validator("limit_price", "stop_loss", "take_profit", mode="before")
    @classmethod
    def parse_optional_price(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        dec = Decimal(str(v))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_PRICE_REQUIRED")
        return dec

    @model_validator(mode="after")
    def validate_payload_semantics(self) -> ForecastPayload:
        if self.kind == ForecastKind.PROBABILITY:
            if not (0.0 <= self.value <= 1.0):
                raise ValueError(f"PROBABILITY_OUT_OF_BOUNDS:{self.value}")
            if self.payoff is None:
                raise ValueError("PAYOFF_STRUCTURE_REQUIRED_FOR_PROBABILITY_FORECAST")
        return self


class ExecutionDecision(BaseModel):
    """Result of cost-aware forecast evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: DecisionAction
    net_edge: float
    forecast_kind: ForecastKind
    reasons: list[str] = Field(default_factory=list)
    signal_intent: SignalIntent | None = None


class CostAwareExecutionMapper:
    """Translates model forecasts into execution intents or abstentions based on net edge and cost basis."""

    def __init__(self, cost_basis: CostBasis) -> None:
        self.cost_basis = cost_basis

    def evaluate_forecast(self, forecast: ForecastPayload) -> ExecutionDecision:
        """Evaluate whether forecast exceeds required safety margin over costs."""
        # 1. Compute net edge per ADR-002 exact-cost semantics
        if forecast.kind == ForecastKind.NET_RETURN:
            # Net return already accounts for costs; do not subtract again
            net_edge = forecast.value
        elif forecast.kind == ForecastKind.GROSS_RETURN:
            # Gross return requires subtracting round-trip cost once
            net_edge = forecast.value - self.cost_basis.estimated_round_trip_cost
        elif forecast.kind == ForecastKind.PROBABILITY:
            # Probability maps to expected gross return, then subtracts cost once
            if forecast.payoff is None:
                raise ValueError("PAYOFF_STRUCTURE_REQUIRED_FOR_PROBABILITY_FORECAST")
            p = forecast.value
            expected_gross = p * forecast.payoff.win_return + (1.0 - p) * forecast.payoff.loss_return
            net_edge = expected_gross - self.cost_basis.estimated_round_trip_cost
        else:
            raise ValueError(f"UNKNOWN_FORECAST_KIND:{forecast.kind}")

        # 2. Check hurdle: net edge must strictly exceed safety margin
        if net_edge > self.cost_basis.safety_margin:
            ts_str = forecast.decision_ts.strftime("%Y%m%d%H%M%S")
            digest = abs(hash((forecast.pair, forecast.value, str(forecast.desired_qty)))) % 100000
            intent_id = f"intent_{forecast.pair}_{ts_str}_{digest}"

            signal_intent = SignalIntent(
                intent_id=intent_id,
                decision_ts=forecast.decision_ts,
                pair=forecast.pair,
                side=forecast.side,
                desired_qty=forecast.desired_qty,
                limit_price=forecast.limit_price,
                stop_loss=forecast.stop_loss,
                take_profit=forecast.take_profit,
                role_preference=forecast.role_preference,
                strategy_id=forecast.strategy_id,
            )
            return ExecutionDecision(
                action=DecisionAction.INTENT,
                net_edge=net_edge,
                forecast_kind=forecast.kind,
                signal_intent=signal_intent,
            )

        return ExecutionDecision(
            action=DecisionAction.ABSTAIN,
            net_edge=net_edge,
            forecast_kind=forecast.kind,
            reasons=["INSUFFICIENT_NET_EDGE"],
            signal_intent=None,
        )
