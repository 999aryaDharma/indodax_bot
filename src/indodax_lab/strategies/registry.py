"""Strategy catalog registry and lifecycle manager (STRAT-01)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable
import yaml
from pydantic import ValidationError

from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import (
    DecisionFrame,
    RegisteredStrategy,
    StrategySpecification,
    _compute_logic_hash,
)


class StrategyRegistry:
    """In-memory registry tracking frozen strategy specifications and implementations."""

    def __init__(self) -> None:
        self._strategies: dict[tuple[str, str], RegisteredStrategy] = {}
        self._parameter_hashes: dict[tuple[str, str], str] = {}
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
        current_param_hash = specification.parameters_hash()
        current_logic_hash = _compute_logic_hash(decide_fn)

        if key in self._strategies:
            prev_param_hash = self._parameter_hashes[key]
            prev_logic_hash = self._logic_hashes[key]

            if prev_param_hash != current_param_hash or prev_logic_hash != current_logic_hash:
                raise ValueError(
                    f"PARAMETER_OR_LOGIC_CHANGE_REQUIRES_VERSION_BUMP: Strategy '{specification.strategy_id}' "
                    f"version '{specification.version}' already registered with different parameters or logic."
                )
            return self._strategies[key]

        registered = RegisteredStrategy(
            specification=specification,
            decide_fn=decide_fn,
        )
        self._strategies[key] = registered
        self._parameter_hashes[key] = current_param_hash
        self._logic_hashes[key] = current_logic_hash
        return registered

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
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("INVALID_YAML_ROOT_DICT_REQUIRED")
        return self.load_specification_from_dict(data)
