"""Declarative strategy catalog and protocol (STRAT-01..C01-01, C07-01)."""

from indodax_lab.strategies.base import (
    DecisionFrame,
    RegisteredStrategy,
    StrategySpecification,
    create_decision_frame,
)
from indodax_lab.strategies.c01 import c01_decide, load_c01_specification
from indodax_lab.strategies.c07 import c07_decide, load_c07_specification
from indodax_lab.strategies.registry import StrategyRegistry

__all__ = [
    "DecisionFrame",
    "RegisteredStrategy",
    "StrategySpecification",
    "StrategyRegistry",
    "create_decision_frame",
    "c01_decide",
    "load_c01_specification",
    "c07_decide",
    "load_c07_specification",
]
