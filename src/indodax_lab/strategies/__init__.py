"""Declarative strategy catalog and protocol (STRAT-01..C01-01, C02-01, C03-01, C07-01)."""

from indodax_lab.strategies.base import (
    DecisionFrame,
    RegisteredStrategy,
    StrategySpecification,
    create_decision_frame,
)
from indodax_lab.strategies.c01 import c01_decide, load_c01_specification
from indodax_lab.strategies.c02 import c02_decide, load_c02_specification
from indodax_lab.strategies.c03 import c03_decide, load_c03_specification
from indodax_lab.strategies.c04 import c04_decide, load_c04_specification
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
    "c02_decide",
    "load_c02_specification",
    "c03_decide",
    "load_c03_specification",
    "c04_decide",
    "load_c04_specification",
    "c07_decide",
    "load_c07_specification",
]
