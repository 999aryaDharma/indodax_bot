import json
import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from indodax_lab.api.auth import Principal, RequestContextMiddleware
from indodax_lab.api.capabilities import Capability
from indodax_lab.api.dependencies import get_request_principal, require_production_read


def test_api_03_2_audits_denial_without_logging_principal_secrets(caplog) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.dependency_overrides[get_request_principal] = lambda: None

    @app.get("/production")
    def production(context: Annotated[object, Depends(require_production_read)]):
        return {"request_id": context.request_id}

    caplog.set_level(logging.INFO, logger="indodax_lab.api.audit")
    response = TestClient(app).get(
        "/production", headers={"x-request-id": "req-denied-1", "authorization": "Bearer secret"}
    )

    assert response.status_code == 403
    assert response.json()["detail"]["request_id"] == "req-denied-1"
    record = next(item for item in caplog.records if item.name == "indodax_lab.api.audit")
    audit = json.loads(record.getMessage())
    assert audit == {
        "actor_class": "anonymous",
        "capability": "production.read",
        "decision": "deny",
        "reason": "IDENTITY_MISSING",
        "request_id": "req-denied-1",
        "resource": "production/*",
        "source_revision": "api-03-policy-v1",
        "timestamp": audit["timestamp"],
    }
    assert "secret" not in record.getMessage()


def test_api_03_2_audits_allowed_read_with_nonsecret_context(caplog) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.dependency_overrides[get_request_principal] = lambda: Principal(
        subject="private-operator-id",
        actor_class="operator",
        capabilities={Capability.PRODUCTION_READ},
    )

    @app.get("/production")
    def production(context: Annotated[object, Depends(require_production_read)]):
        return {"request_id": context.request_id}

    caplog.set_level(logging.INFO, logger="indodax_lab.api.audit")
    response = TestClient(app).get("/production")

    assert response.status_code == 200
    record = next(item for item in caplog.records if item.name == "indodax_lab.api.audit")
    audit = json.loads(record.getMessage())
    assert audit["actor_class"] == "operator"
    assert audit["capability"] == "production.read"
    assert audit["decision"] == "allow"
    assert audit["reason"] == "CAPABILITY_GRANTED"
    assert audit["request_id"] == response.json()["request_id"]
    assert "private-operator-id" not in record.getMessage()
