"""Backtest, simulation, ledger, and execution subsystem.

The package keeps its historical flat exports through lazy attribute loading.
Lazy loading also prevents the shared decision contract from importing the
backtest package's execution graph while the package is still initializing.
"""

from __future__ import annotations

from importlib import import_module
from typing import Final

from indodax_lab.backtest.costs import (
    CostScheduleInterval,
    CostScheduleResolution,
    CostScheduleTable,
    OrderRole,
    OrderSide,
    UnknownCostScheduleError,
    load_cost_schedule_table,
    lookup_cost,
)

_LAZY_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "AccountType": ("indodax_lab.backtest.ledger", "AccountType"),
    "BacktestResult": ("indodax_lab.backtest.result", "BacktestResult"),
    "ConservativeExecutionSimulator": ("indodax_lab.backtest.execution", "ConservativeExecutionSimulator"),
    "CostStressMetrics": ("indodax_lab.backtest.metrics", "CostStressMetrics"),
    "DuplicateFillError": ("indodax_lab.backtest.ledger", "DuplicateFillError"),
    "ExecutionResult": ("indodax_lab.backtest.events", "ExecutionResult"),
    "ExecutionStatus": ("indodax_lab.backtest.events", "ExecutionStatus"),
    "Fill": ("indodax_lab.backtest.orders", "Fill"),
    "InsufficientQuantityError": ("indodax_lab.backtest.ledger", "InsufficientQuantityError"),
    "LedgerTransaction": ("indodax_lab.backtest.ledger", "LedgerTransaction"),
    "MarketBar": ("indodax_lab.backtest.events", "MarketBar"),
    "PerformanceMetrics": ("indodax_lab.backtest.metrics", "PerformanceMetrics"),
    "PortfolioRiskManager": ("indodax_lab.backtest.risk", "PortfolioRiskManager"),
    "Position": ("indodax_lab.backtest.ledger", "Position"),
    "Posting": ("indodax_lab.backtest.ledger", "Posting"),
    "ProfitFactorResult": ("indodax_lab.backtest.metrics", "ProfitFactorResult"),
    "ReplayBacktestEngine": ("indodax_lab.backtest.engine", "ReplayBacktestEngine"),
    "ResearchLedger": ("indodax_lab.backtest.ledger", "ResearchLedger"),
    "RiskAssessmentResult": ("indodax_lab.backtest.risk", "RiskAssessmentResult"),
    "RiskPolicy": ("indodax_lab.backtest.risk", "RiskPolicy"),
    "SignalIntent": ("indodax_lab.contracts.decision", "SignalIntent"),
    "calculate_equity": ("indodax_lab.backtest.metrics", "calculate_equity"),
    "compute_performance_metrics": ("indodax_lab.backtest.metrics", "compute_performance_metrics"),
}


def __getattr__(name: str):
    """Resolve historical flat exports on first access."""

    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "AccountType",
    "BacktestResult",
    "ConservativeExecutionSimulator",
    "CostScheduleInterval",
    "CostScheduleResolution",
    "CostScheduleTable",
    "CostStressMetrics",
    "DuplicateFillError",
    "ExecutionResult",
    "ExecutionStatus",
    "Fill",
    "InsufficientQuantityError",
    "LedgerTransaction",
    "MarketBar",
    "OrderRole",
    "OrderSide",
    "PerformanceMetrics",
    "PortfolioRiskManager",
    "Position",
    "Posting",
    "ProfitFactorResult",
    "ReplayBacktestEngine",
    "ResearchLedger",
    "RiskAssessmentResult",
    "RiskPolicy",
    "SignalIntent",
    "UnknownCostScheduleError",
    "calculate_equity",
    "compute_performance_metrics",
    "load_cost_schedule_table",
    "lookup_cost",
]
