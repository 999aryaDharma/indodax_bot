"""Composition root for the read-only live Production control-plane API."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request

from indodax_lab.api.auth import Principal, RequestContextMiddleware
from indodax_lab.api.routers.production import router as production_router
from indodax_lab.api.services.production_read import ProductionReadService, VenueAccountProvider


def create_app(
    *,
    production_namespace: str | None,
    production_state_root: str | Path | None,
    venue_account_source: VenueAccountProvider | None,
    mode_store: Any = None,
    execution_store: Any = None,
    risk_engine: Any = None,
    principal_resolver: Callable[[Request], Principal | None] | None = None,
) -> FastAPI:
    """Build Production reads from explicit Production-owned configuration.

    Credential acquisition and authentication-provider setup belong to the existing
    Production runtime. This app never reads environment credentials or creates venue clients.
    """
    namespace = production_namespace.strip() if production_namespace else ""
    normalized = namespace.lower().replace("_", "-")
    if (
        not namespace
        or normalized in {"research", "shadow", "tournament", "portfolio-shadow", "prod-paper"}
        or normalized.startswith(("research-", "shadow-", "tournament-", "portfolio-shadow-"))
    ):
        raise ValueError("PRODUCTION_NAMESPACE_REQUIRED")
    if production_state_root is None or not str(production_state_root).strip():
        raise ValueError("PRODUCTION_STATE_ROOT_REQUIRED")
    configured_root = Path(production_state_root)
    if not configured_root.is_absolute():
        raise ValueError("PRODUCTION_STATE_ROOT_MUST_BE_ABSOLUTE")
    root = configured_root.resolve()
    if venue_account_source is not None and getattr(venue_account_source, "authority", None) != (
        "production.indodax.account"
    ):
        raise ValueError("PRODUCTION_ACCOUNT_PROVIDER_REQUIRED")

    service = ProductionReadService(
        mode_store=mode_store,
        execution_store=execution_store,
        risk_engine=risk_engine,
        venue_account_source=venue_account_source,
        production_namespace=namespace,
        production_state_root=root,
    )
    app = FastAPI(title="Indodax Systematic Production API", version="1.0.0")
    app.add_middleware(RequestContextMiddleware)
    app.include_router(production_router)
    app.state.resolve_production_service = lambda: service
    app.state.principal_resolver = principal_resolver

    @app.middleware("http")
    async def install_trusted_principal(request: Request, call_next):
        resolver = request.app.state.principal_resolver
        if callable(resolver):
            request.state.principal = resolver(request)
        return await call_next(request)

    return app
