"""Explicit environment composition for the read-only Production API."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from indodax_lab.api.app import create_app
from indodax_lab.api.auth import tailscale_principal_resolver
from indodax_lab.execution.indodax_readonly import IndodaxReadOnlyClient, VenueAccountSnapshot


class ProductionIndodaxAccountProvider:
    """Production marker around the existing Indodax view-only client."""

    authority = "production.indodax.account"

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_account_snapshot(self) -> VenueAccountSnapshot:
        return self._client.get_account_snapshot()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(client=<redacted>)"


def create_production_app_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    client_factory: Callable[..., Any] = IndodaxReadOnlyClient,
) -> FastAPI:
    """Compose Production reads; no credentials are read until this is explicitly called."""
    env = os.environ if environ is None else environ
    api_key = env.get("INDODAX_VIEW_API_KEY", "")
    secret_key = env.get("INDODAX_VIEW_SECRET_KEY", "")
    namespace = env.get("PRODUCTION_NAMESPACE", "")
    state_root = env.get("PRODUCTION_STATE_ROOT", "")
    allowlist_text = env.get("PRODUCTION_OPERATOR_ALLOWLIST", "")

    configured_root = Path(state_root) if state_root.strip() else None
    if (
        not api_key.strip()
        or not secret_key.strip()
        or not namespace.strip()
        or configured_root is None
        or not configured_root.is_absolute()
    ):
        raise ValueError("PRODUCTION_RUNTIME_CONFIGURATION_REQUIRED")
    if namespace.strip().casefold() != "production":
        raise ValueError("PRODUCTION_NAMESPACE_REQUIRED")

    allowlist = tuple(value.strip() for value in allowlist_text.split(",") if value.strip())
    if not allowlist or any(any(char.isspace() for char in value) for value in allowlist):
        raise ValueError("PRODUCTION_OPERATOR_ALLOWLIST_REQUIRED")

    account_provider = ProductionIndodaxAccountProvider(
        client_factory(api_key=api_key, secret_key=secret_key)
    )
    return create_app(
        production_namespace=namespace,
        production_state_root=configured_root,
        venue_account_source=account_provider,
        principal_resolver=tailscale_principal_resolver(allowlist),
    )


def main() -> None:
    """Run the Production API on loopback behind Tailscale Serve."""
    port_text = os.environ.get("PRODUCTION_API_PORT", "8000")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("PRODUCTION_API_PORT_INVALID") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PRODUCTION_API_PORT_INVALID")

    import uvicorn

    uvicorn.run(
        create_production_app_from_env(),
        host="127.0.0.1",
        port=port,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
