"""Fail-closed Production API dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request

from indodax_lab.api.audit import record_access_decision
from indodax_lab.api.auth import (
    ActorClass,
    PolicyContext,
    Principal,
    ensure_request_id,
)
from indodax_lab.api.capabilities import Capability


def get_request_principal(request: Request) -> Principal | None:
    """Read only a principal installed by trusted application auth middleware."""
    principal = getattr(request.state, "principal", None)
    return principal if isinstance(principal, Principal) else None


def require_production_read(
    request: Request,
    principal: Annotated[Principal | None, Depends(get_request_principal)],
) -> PolicyContext:
    request_id = ensure_request_id(request)
    actor_class = principal.actor_class if principal is not None else ActorClass.ANONYMOUS
    reason = "CAPABILITY_GRANTED"

    if principal is None or actor_class is ActorClass.ANONYMOUS:
        decision, reason = "deny", "IDENTITY_MISSING"
    elif actor_class is ActorClass.RESEARCH:
        decision, reason = "deny", "RESEARCH_ACTOR"
    elif Capability.PRODUCTION_READ not in principal.capabilities:
        decision, reason = "deny", "CAPABILITY_MISSING"
    else:
        decision = "allow"

    record_access_decision(
        request_id=request_id,
        actor_class=actor_class,
        capability=Capability.PRODUCTION_READ,
        decision=decision,
        reason=reason,
    )
    if decision == "deny":
        raise HTTPException(
            status_code=403,
            detail={"code": "PRODUCTION_READ_FORBIDDEN", "request_id": request_id},
        )

    return PolicyContext(
        request_id=request_id,
        actor_class=actor_class,
        capability=Capability.PRODUCTION_READ,
        as_of=datetime.now(UTC),
    )


def get_production_service(
    request: Request,
    _context: Annotated[PolicyContext, Depends(require_production_read)],
) -> Any:
    """Resolve a Production service only after the read policy succeeds."""
    resolver = getattr(request.app.state, "resolve_production_service", None)
    if not callable(resolver):
        raise HTTPException(
            status_code=503,
            detail={"code": "PRODUCTION_SERVICE_UNAVAILABLE", "request_id": _context.request_id},
        )
    return resolver()
