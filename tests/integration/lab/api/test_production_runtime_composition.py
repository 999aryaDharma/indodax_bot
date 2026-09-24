from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from starlette.requests import Request

from indodax_lab.execution.indodax_readonly import VenueAccountSnapshot, VenueBalance
from indodax_lab.runtimes.production.control_plane import (
    create_production_app_from_env,
    main,
)


class FakeReadOnlyClient:
    def __init__(self, api_key: str, secret_key: str) -> None:
        self.api_key = api_key
        self.secret_key = secret_key

    def get_account_snapshot(self) -> VenueAccountSnapshot:
        if hasattr(self, "venue_calls"):
            self.venue_calls.append(True)
        return VenueAccountSnapshot(
            server_time=datetime(2026, 9, 24, tzinfo=UTC),
            balances={"idr": VenueBalance("idr", Decimal("10"), Decimal("0"))},
        )


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "INDODAX_VIEW_API_KEY": "test-api-key",
        "INDODAX_VIEW_SECRET_KEY": "test-secret-key",
        "PRODUCTION_NAMESPACE": "production",
        "PRODUCTION_STATE_ROOT": str(Path.cwd() / "fake-production-state"),
        "PRODUCTION_OPERATOR_ALLOWLIST": "arya@example.com",
    }
    values.update(overrides)
    return values


def test_api_07_2_composes_only_view_client_from_explicit_production_configuration() -> None:
    app = create_production_app_from_env(_environment(), client_factory=FakeReadOnlyClient)

    service = app.state.resolve_production_service()
    snapshot = service.venue_account_source.get_account_snapshot()
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers=Headers({"Tailscale-User-Login": "arya@example.com"}),
    )
    principal = app.state.principal_resolver(request)

    assert snapshot.balances["idr"].available == Decimal("10")
    assert service.production_namespace == "production"
    assert principal is not None
    assert principal.capabilities == {"production.read"}
    assert "test-api-key" not in repr(service.venue_account_source)
    assert "test-secret-key" not in repr(service.venue_account_source)

    resolver = app.state.principal_resolver
    app.state.principal_resolver = lambda request: resolver(
        Request({**request.scope, "client": ("127.0.0.1", 1234)})
    )
    response = TestClient(app).get(
        "/api/v1/production/portfolio",
        headers={"Tailscale-User-Login": "arya@example.com"},
    )
    assert response.status_code == 200
    assert "test-api-key" not in response.text
    assert "test-secret-key" not in response.text


@pytest.mark.parametrize(
    "override",
    [
        {"INDODAX_VIEW_API_KEY": ""},
        {"INDODAX_VIEW_SECRET_KEY": ""},
        {"PRODUCTION_NAMESPACE": "research_shadow"},
        {"PRODUCTION_NAMESPACE": "production_main"},
        {"PRODUCTION_OPERATOR_ALLOWLIST": ""},
    ],
)
def test_api_07_3_invalid_runtime_configuration_fails_before_venue_request(override) -> None:
    venue_calls: list[bool] = []

    def factory(api_key: str, secret_key: str):
        client = FakeReadOnlyClient(api_key, secret_key)
        client.venue_calls = venue_calls
        return client

    with pytest.raises(ValueError):
        create_production_app_from_env(_environment(**override), client_factory=factory)

    assert venue_calls == []


def test_api_07_4_asgi_entrypoint_binds_loopback_without_proxy_header_rewrite(monkeypatch) -> None:
    monkeypatch.setenv("INDODAX_VIEW_API_KEY", "test-api-key")
    monkeypatch.setenv("INDODAX_VIEW_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("PRODUCTION_NAMESPACE", "production")
    monkeypatch.setenv("PRODUCTION_STATE_ROOT", str(Path.cwd() / "fake-production-state"))
    monkeypatch.setenv("PRODUCTION_OPERATOR_ALLOWLIST", "arya@example.com")
    monkeypatch.setenv("PRODUCTION_API_PORT", "8123")
    called: dict[str, object] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: called.update(app=app, **kwargs))

    main()

    assert called["host"] == "127.0.0.1"
    assert called["port"] == 8123
    assert called["proxy_headers"] is False
