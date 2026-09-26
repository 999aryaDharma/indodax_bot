"""Declarative strategy catalog and protocol."""

from indodax_lab.strategies.base import (
    DecisionFrame,
    DraftRef,
    RegisteredStrategy,
    StrategyComponentMetadata,
    StrategySpecification,
    create_decision_frame,
)
from indodax_lab.strategies.c01 import c01_decide, load_c01_specification
from indodax_lab.strategies.c02 import c02_decide, load_c02_specification
from indodax_lab.strategies.c03 import c03_decide, load_c03_specification
from indodax_lab.strategies.c04 import c04_decide, load_c04_specification
from indodax_lab.strategies.c05 import c05_decide, load_c05_specification
from indodax_lab.strategies.c06 import c06_decide, load_c06_specification
from indodax_lab.strategies.c08 import c08_decide, load_c08_specification
from indodax_lab.strategies.c07 import c07_decide, load_c07_specification
from indodax_lab.strategies.c10 import c10_decide, load_c10_specification
from indodax_lab.strategies.registry import StrategyRegistry
from indodax_lab.strategies.s01 import load_s01_specification, s01_decide
from indodax_lab.strategies.s02 import load_s02_specification, s02_decide
from indodax_lab.strategies.store import StrategyService, StrategyStore

__all__ = [
    "DecisionFrame",
    "DraftRef",
    "RegisteredStrategy",
    "StrategyComponentMetadata",
    "StrategySpecification",
    "StrategyRegistry",
    "StrategyService",
    "StrategyStore",
    "create_decision_frame",
    "c01_decide",
    "load_c01_specification",
    "c02_decide",
    "load_c02_specification",
    "c03_decide",
    "load_c03_specification",
    "c04_decide",
    "load_c04_specification",
    "c05_decide",
    "load_c05_specification",
    "c06_decide",
    "load_c06_specification",
    "c08_decide",
    "load_c08_specification",
    "c07_decide",
    "load_c07_specification",
    "c10_decide",
    "load_c10_specification",
    "s01_decide",
    "load_s01_specification",
    "s02_decide",
    "load_s02_specification",
]
