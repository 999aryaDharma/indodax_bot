"""Conservative execution simulator without lookahead and with realistic costs (SIM-01)."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from indodax_lab.backtest.costs import CostScheduleTable, OrderRole, OrderSide, lookup_cost
from indodax_lab.backtest.events import ExecutionResult, ExecutionStatus, MarketBar
from indodax_lab.backtest.orders import Fill
from indodax_lab.contracts.decision import SignalIntent


class ConservativeExecutionSimulator:
    """Simulates conservative fills without lookahead bias and with realistic costs."""

    def __init__(
        self,
        cost_schedule_table: CostScheduleTable,
        max_participation_rate: Decimal = Decimal("0.10"),
        require_trade_through_for_maker: bool = True,
        market: str = "spot_idr",
        quantity_precision: int = 8,
    ) -> None:
        self.cost_schedule_table = cost_schedule_table
        self.max_participation_rate = max_participation_rate
        self.require_trade_through_for_maker = require_trade_through_for_maker
        self.market = market
        if not max_participation_rate.is_finite() or not 0 < max_participation_rate <= 1:
            raise ValueError("INVALID_PARTICIPATION_RATE")
        if isinstance(quantity_precision, bool) or not isinstance(quantity_precision, int) or not 0 <= quantity_precision <= 18:
            raise ValueError("INVALID_QUANTITY_PRECISION")
        self.quantity_precision = quantity_precision
        self.execution_version = "causal-bar-proxy-v2"

    def simulate_execution(self, intent: SignalIntent, bar: MarketBar) -> ExecutionResult:
        """Simulate order execution on a subsequent eligible market bar.

        Enforces:
        1. Next-open causal execution (SIM-01-AC1: rejects same-close / past bar execution).
        2. Conservative depth / min-size gating (SIM-01-AC2: rejects or produces partial fills).
        3. Strict maker fill rules (SIM-01-AC3: limit touch alone does not fill).
        """
        bar = MarketBar.model_validate(bar.model_dump())
        intent = SignalIntent.model_validate(intent.model_dump())
        if intent.role_preference == OrderRole.MAKER and intent.limit_price is None:
            return ExecutionResult(intent_id=intent.intent_id, status=ExecutionStatus.REJECTED,
                                   reason_code="MAKER_LIMIT_REQUIRED")
        if intent.pair != bar.pair:
            return ExecutionResult(intent_id=intent.intent_id, status=ExecutionStatus.REJECTED,
                                   reason_code="PAIR_MISMATCH")
        # SIM-01-AC1: Same-close execution ditolak.
        # Execution must happen strictly after decision_ts.
        if bar.close_time <= intent.decision_ts or bar.open_time < intent.decision_ts:
            return ExecutionResult(
                intent_id=intent.intent_id,
                status=ExecutionStatus.REJECTED,
                reason_code="SAME_CLOSE_EXECUTION_FORBIDDEN",
            )

        # Determine fill price and role
        if intent.role_preference == OrderRole.MAKER and intent.limit_price is not None:
            fill_time = bar.available_at
            liquidity = bar.base_volume
            limit_p = intent.limit_price
            if intent.side == OrderSide.BUY:
                if bar.low > limit_p:
                    return ExecutionResult(
                        intent_id=intent.intent_id,
                        status=ExecutionStatus.REJECTED,
                        reason_code="LIMIT_UNREACHED",
                    )
                # SIM-01-AC3: Limit touch tidak otomatis maker fill
                if bar.low == limit_p and self.require_trade_through_for_maker:
                    return ExecutionResult(
                        intent_id=intent.intent_id,
                        status=ExecutionStatus.REJECTED,
                        reason_code="LIMIT_TOUCH_NO_FILL",
                    )
                fill_price = limit_p
                exec_role = OrderRole.MAKER
            else:  # SELL
                if bar.high < limit_p:
                    return ExecutionResult(
                        intent_id=intent.intent_id,
                        status=ExecutionStatus.REJECTED,
                        reason_code="LIMIT_UNREACHED",
                    )
                if bar.high == limit_p and self.require_trade_through_for_maker:
                    return ExecutionResult(
                        intent_id=intent.intent_id,
                        status=ExecutionStatus.REJECTED,
                        reason_code="LIMIT_TOUCH_NO_FILL",
                    )
                fill_price = limit_p
                exec_role = OrderRole.MAKER
        else:
            # Taker market order fills at bar open
            fill_price = bar.open
            exec_role = OrderRole.TAKER
            fill_time = bar.open_time
            liquidity = bar.open_liquidity_base_volume
            if liquidity is None:
                return ExecutionResult(intent_id=intent.intent_id, status=ExecutionStatus.REJECTED,
                                       reason_code="MISSING_CAUSAL_LIQUIDITY")
            # This version accepts at most one bar interval of liquidity age.
            if bar.open_time - bar.open_liquidity_available_at > bar.close_time - bar.open_time:
                return ExecutionResult(intent_id=intent.intent_id, status=ExecutionStatus.REJECTED,
                                       reason_code="STALE_CAUSAL_LIQUIDITY")

        # Lookup time-valid exchange costs
        schedule = lookup_cost(
            self.cost_schedule_table,
            market=self.market,
            side=intent.side,
            role=exec_role,
            fee_basis_ts=(intent.decision_ts if intent.limit_price is not None else fill_time),
        )

        # SIM-01-AC2: Insufficient depth dan min-size checks
        desired_notional = intent.desired_qty * fill_price
        if desired_notional < schedule.min_notional:
            return ExecutionResult(
                intent_id=intent.intent_id,
                status=ExecutionStatus.REJECTED,
                reason_code="MIN_NOTIONAL_VIOLATION",
            )

        max_fillable_qty = (liquidity * self.max_participation_rate).quantize(
            Decimal(10) ** -self.quantity_precision, rounding=ROUND_DOWN)
        if max_fillable_qty <= Decimal("0"):
            return ExecutionResult(
                intent_id=intent.intent_id,
                status=ExecutionStatus.REJECTED,
                reason_code="INSUFFICIENT_DEPTH",
            )

        if intent.desired_qty <= max_fillable_qty:
            filled_qty = intent.desired_qty
            remaining_qty = Decimal("0")
            status = ExecutionStatus.FILLED
            reason = "SUCCESS"
        else:
            filled_qty = max_fillable_qty
            remaining_qty = intent.desired_qty - max_fillable_qty
            if (filled_qty * fill_price) < schedule.min_notional:
                return ExecutionResult(
                    intent_id=intent.intent_id,
                    status=ExecutionStatus.REJECTED,
                    reason_code="MIN_NOTIONAL_VIOLATION_AFTER_PARTIAL",
                )
            status = ExecutionStatus.PARTIAL
            reason = "PARTIAL_DEPTH"

        filled_qty = filled_qty.quantize(Decimal(10) ** -self.quantity_precision, rounding=ROUND_DOWN)
        if filled_qty <= 0 or filled_qty * fill_price < schedule.min_notional:
            return ExecutionResult(intent_id=intent.intent_id, status=ExecutionStatus.REJECTED,
                                   reason_code="MIN_NOTIONAL_VIOLATION_AFTER_PRECISION")
        remaining_qty = intent.desired_qty - filled_qty
        if remaining_qty > 0:
            status = ExecutionStatus.PARTIAL
        gross = filled_qty * fill_price
        fees_unrounded = gross * schedule.total_rate
        if schedule.precision == 0:
            fees = fees_unrounded.quantize(Decimal("1"))
        else:
            fees = fees_unrounded.quantize(Decimal(10) ** -schedule.precision)

        fee_components = {
            "service": gross * schedule.service_fee_rate,
            "tax": gross * schedule.tax_rate,
            "exchange": gross * schedule.exchange_fee_rate,
        }

        fill = Fill(
            fill_id=f"fill-{intent.intent_id}",
            order_id=f"ord-{intent.intent_id}",
            event_id=f"evt-{fill_time.isoformat()}",
            pair=intent.pair,
            side=intent.side,
            role=exec_role,
            qty=filled_qty,
            price=fill_price,
            fees=fees,
            timestamp=fill_time,
            fee_components=fee_components,
        )

        return ExecutionResult(
            intent_id=intent.intent_id,
            status=status,
            fill=fill,
            filled_qty=filled_qty,
            remaining_qty=remaining_qty,
            fill_price=fill_price,
            reason_code=reason,
        )
