"""Capability-protected, read-only Production routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from indodax_lab.api.auth import PolicyContext, ensure_request_id
from indodax_lab.api.contracts.common import ApiEnvelope, Provenance
from indodax_lab.api.dependencies import get_production_service, require_production_read
from indodax_lab.api.services.production_read import ProductionReadService

router = APIRouter(prefix="/api/v1/production", tags=["production"])
Service = Annotated[ProductionReadService, Depends(get_production_service)]
Policy = Annotated[PolicyContext, Depends(require_production_read)]


def _response(request: Request, service: ProductionReadService, field: str) -> dict[str, Any]:
    snapshot = service.snapshot(request_id=ensure_request_id(request))
    data = getattr(snapshot, field)
    status = snapshot.status if field == "overview" else data.evidence.status
    envelope = ApiEnvelope(
        request_id=snapshot.request_id,
        as_of=snapshot.as_of,
        source_revision=snapshot.source_revision,
        status=status,
        data=data,
        provenance=Provenance(
            source=snapshot.provenance.source,
            revision=snapshot.source_revision,
        ),
    )
    return envelope.model_dump(mode="json")


@router.get("/snapshot")
def read_snapshot(request: Request, service: Service, _policy: Policy) -> dict[str, Any]:
    snapshot = service.snapshot(request_id=ensure_request_id(request))
    return {
        "request_id": snapshot.request_id,
        "as_of": snapshot.as_of.isoformat(),
        "source_revision": snapshot.source_revision,
        "status": snapshot.status,
        "data": snapshot.model_dump(mode="json"),
        "provenance": {
            "source": snapshot.provenance.source,
            "revision": snapshot.source_revision,
        },
    }


def _endpoint(field: str) -> Callable[..., dict[str, Any]]:
    def endpoint(request: Request, service: Service, _policy: Policy) -> dict[str, Any]:
        return _response(request, service, field)

    endpoint.__name__ = f"read_{field}"
    return endpoint


for _field in (
    "overview",
    "mode",
    "portfolio",
    "positions",
    "orders",
    "fills",
    "reconciliation",
    "risk",
    "release",
    "audit",
):
    router.add_api_route(
        f"/{_field.replace('_', '-')}",
        _endpoint(_field),
        methods=["GET"],
        name=_field,
    )


def _page(request: Request, service: ProductionReadService, field: str, offset: int, limit: int):
    response = _response(request, service, field)
    rows = response["data"]["data"]
    response["data"]["data"] = rows[offset : offset + limit]
    response["data"]["total"] = len(rows)
    response["data"]["offset"] = offset
    response["data"]["limit"] = limit
    return response


@router.get("/orders/page")
def read_orders_page(
    request: Request,
    service: Service,
    _policy: Policy,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return _page(request, service, "orders", offset, limit)


@router.get("/fills/page")
def read_fills_page(
    request: Request,
    service: Service,
    _policy: Policy,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return _page(request, service, "fills", offset, limit)
