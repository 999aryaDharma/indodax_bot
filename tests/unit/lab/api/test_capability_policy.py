from datetime import UTC
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from indodax_lab.api.auth import ActorClass, Principal
from indodax_lab.api.capabilities import Capability
from indodax_lab.api.dependencies import (
    get_production_service,
    get_request_principal,
    require_production_read,
)


@pytest.mark.parametrize("principal", [None, "anonymous", "research", "no-capability"])
def test_api_03_0_denies_missing_or_nonproduction_identity_before_service_resolution(
    principal: object,
) -> None:
    resolved: list[bool] = []
    app = FastAPI()

    def injected_principal() -> Principal | None:
        if principal == "anonymous":
            return Principal(
                subject="anon",
                actor_class=ActorClass.ANONYMOUS,
                capabilities={Capability.PRODUCTION_READ},
            )
        if principal == "research":
            return Principal(
                subject="research-user",
                actor_class=ActorClass.RESEARCH,
                capabilities={Capability.PRODUCTION_READ, Capability.RESEARCH_READ},
            )
        if principal == "no-capability":
            return Principal(subject="operator", actor_class=ActorClass.OPERATOR)
        return None

    app.dependency_overrides[get_request_principal] = injected_principal

    @app.get("/production")
    def production(
        service: Annotated[object, Depends(get_production_service)],
    ) -> dict[str, str]:
        return {"service": str(service)}

    app.state.resolve_production_service = lambda: resolved.append(True) or object()

    response = TestClient(app).get("/production")
    assert response.status_code == 403
    assert resolved == []


def test_api_03_1_research_capability_does_not_grant_production_read() -> None:
    app = FastAPI()
    app.dependency_overrides[get_request_principal] = lambda: Principal(
        subject="research-1",
        actor_class=ActorClass.RESEARCH,
        capabilities={Capability.RESEARCH_READ},
    )

    @app.get("/production")
    def production(context: Annotated[object, Depends(require_production_read)]):
        return {"request_id": context.request_id}

    response = TestClient(app).get("/production")
    assert response.status_code == 403


def test_api_03_2_explicit_production_identity_is_allowed() -> None:
    app = FastAPI()
    app.dependency_overrides[get_request_principal] = lambda: Principal(
        subject="operator-1",
        actor_class=ActorClass.OPERATOR,
        capabilities={Capability.PRODUCTION_READ},
    )

    @app.get("/production")
    def production(context: Annotated[object, Depends(require_production_read)]):
        assert context.actor_class is ActorClass.OPERATOR
        assert context.capability is Capability.PRODUCTION_READ
        assert context.as_of.tzinfo is UTC
        return {"request_id": context.request_id}

    response = TestClient(app).get("/production", headers={"x-request-id": "req-explicit"})
    assert response.status_code == 200
    assert response.json() == {"request_id": "req-explicit"}
