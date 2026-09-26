"""Strategy catalog registry and lifecycle manager (STRAT-01)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import (
    DecisionFrame,
    RegisteredStrategy,
    StrategySpecification,
    _compute_logic_hash,
)


@dataclass(frozen=True)
class BuiltinStrategyImplementation:
    component_id: str
    decide_fn: Callable[[DecisionFrame], list[SignalIntent]]
    source_path: Path


def component_id_for_strategy(strategy_id: str) -> str:
    """Resolve a built-in component suffix without importing user-provided modules."""
    if not strategy_id or any(token in strategy_id for token in ("/", "\\", "..", ":")):
        raise ValueError("UNAPPROVED_STRATEGY_ID")
    component_id = strategy_id.rsplit("-", 1)[-1]
    if component_id not in {"C02", "C07"}:
        raise ValueError(f"UNKNOWN_BUILTIN_STRATEGY_ID:{strategy_id}")
    return component_id


def builtin_strategy_implementation(strategy_id: str) -> BuiltinStrategyImplementation:
    """Return one of the statically imported seed implementations."""
    component_id = component_id_for_strategy(strategy_id)
    if component_id == "C02":
        from indodax_lab.strategies import c02

        return BuiltinStrategyImplementation(component_id, c02.c02_decide, Path(c02.__file__))
    from indodax_lab.strategies import c07

    return BuiltinStrategyImplementation(component_id, c07.c07_decide, Path(c07.__file__))


class StrategyRegistry:
    """In-memory registry tracking frozen strategy specifications and implementations."""

    def __init__(self) -> None:
        self._strategies: dict[tuple[str, str], RegisteredStrategy] = {}
        self._specification_hashes: dict[tuple[str, str], str] = {}
        self._logic_hashes: dict[tuple[str, str], str] = {}

    def register(
        self,
        specification: StrategySpecification,
        decide_fn: Callable[[DecisionFrame], list[SignalIntent]],
    ) -> RegisteredStrategy:
        """Register a strategy candidate under its specification and immutable version.

        Fails if a strategy with the same ID and version is registered with changed
        parameters or changed logic.
        """
        key = (specification.strategy_id, specification.version)
        current_specification_hash = specification.identity_hash()
        current_logic_hash = _compute_logic_hash(decide_fn)

        if key in self._strategies:
            prev_specification_hash = self._specification_hashes[key]
            prev_logic_hash = self._logic_hashes[key]

            if (
                prev_specification_hash != current_specification_hash
                or prev_logic_hash != current_logic_hash
            ):
                raise ValueError(
                    "PARAMETER_OR_LOGIC_CHANGE_REQUIRES_VERSION_BUMP: "
                    f"Strategy '{specification.strategy_id}' version '{specification.version}' "
                    "already registered with different parameters or logic."
                )
            return self._strategies[key]

        registered = RegisteredStrategy(
            specification=specification,
            decide_fn=decide_fn,
        )
        self._strategies[key] = registered
        self._specification_hashes[key] = current_specification_hash
        self._logic_hashes[key] = current_logic_hash
        return registered

    def register_builtin(self, specification: StrategySpecification) -> RegisteredStrategy:
        """Register an allowlisted seed component using its statically bound function."""
        implementation = builtin_strategy_implementation(specification.strategy_id)
        return self.register(specification, implementation.decide_fn)

    def get(self, strategy_id: str, version: str) -> RegisteredStrategy | None:
        """Retrieve registered strategy by strategy_id and semantic version."""
        return self._strategies.get((strategy_id, version))

    def list_strategies(self) -> list[StrategySpecification]:
        """List all registered strategy specifications."""
        return [strat.specification for strat in self._strategies.values()]

    def load_specification_from_dict(self, data: dict[str, Any]) -> StrategySpecification:
        """Parse and strictly validate a strategy specification dictionary.

        Rejects any unrecognized or extra fields.
        """
        try:
            return StrategySpecification(**data)
        except ValidationError as err:
            raise ValueError(f"UNKNOWN_CONFIG_FIELDS: {err}") from err

    def load_specification_from_yaml(self, path: str | Path) -> StrategySpecification:
        """Load and strictly validate a strategy specification from YAML file."""
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"STRATEGY_CONFIG_NOT_FOUND: {yaml_path}")
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("INVALID_YAML_ROOT_DICT_REQUIRED")
        return self.load_specification_from_dict(data)
