from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from indodax_lab.api.app import create_app
from indodax_lab.api.auth import ActorClass, Principal
from indodax_lab.api.capabilities import Capability
from indodax_lab.control.mode import ExecutionMode
from indodax_lab.execution.indodax_readonly import VenueAccountSnapshot, VenueBalance


class FakeReadOnlyIndodaxClient:
    authority = "production.indodax.account"

    def get_account_snapshot(self):
        return VenueAccountSnapshot(
            server_time=datetime.now(UTC),
            balances={"idr": VenueBalance("idr", Decimal("1250000"), Decimal("100"))},
        )


class FakeModeStore:
    def get_effective_mode(self):
        return ExecutionMode.SHADOW

    def get_requested_mode(self):
        return ExecutionMode.SHADOW

    def verify_journal_integrity(self):
        return True

    def get_journal(self):
        return (
            {
                "sequence": 2,
                "entry_hash": "mode-r2",
                "timestamp_utc": "2026-09-24T04:00:00+00:00",
            },
        )


def client(principal=None, **kwargs):
    app = create_app(
        production_namespace="production_main",
        production_state_root="D:/var/lib/indodax",
        venue_account_source=FakeReadOnlyIndodaxClient(),
        **kwargs,
    )
    if principal is not None:
        app.state.principal_resolver = lambda request: principal
    return TestClient(app)


def test_api_02_0_portfolio_route_requires_capability_and_returns_live_account_evidence():
    operator = Principal(
        subject="operator-1",
        actor_class=ActorClass.OPERATOR,
        capabilities=frozenset({Capability.PRODUCTION_READ}),
    )
    response = client(operator).get("/api/v1/production/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "AVAILABLE"
    assert body["data"]["evidence"]["source"] == "production.venue_account"
    assert body["data"]["evidence"]["freshness"] == "FRESH"
    assert body["data"]["balances"][0]["total"] == "1250100"
    assert "api_key" not in response.text.lower()
    assert "secret_key" not in response.text.lower()


def test_api_02_1_anonymous_and_research_are_denied_before_provider_resolution():
    for principal in (
        None,
        Principal(
            subject="research-1",
            actor_class=ActorClass.RESEARCH,
            capabilities=frozenset({Capability.PRODUCTION_READ}),
        ),
    ):
        app = create_app(
            production_namespace="production_main",
            production_state_root="D:/var/lib/indodax",
            venue_account_source=FakeReadOnlyIndodaxClient(),
            principal_resolver=lambda _request, current=principal: current,
        )
        app.state.resolve_production_service = lambda: (_ for _ in ()).throw(
            AssertionError("service resolved before authorization")
        )
        response = TestClient(app).get("/api/v1/production/portfolio")
        assert response.status_code == 403


def test_api_02_2_missing_production_provider_returns_safe_unavailable():
    operator = Principal(
        subject="operator-1",
        actor_class=ActorClass.OPERATOR,
        capabilities=frozenset({Capability.PRODUCTION_READ}),
    )
    app = create_app(
        production_namespace="production_main",
        production_state_root="D:/var/lib/indodax",
        venue_account_source=None,
    )
    app.state.principal_resolver = lambda request: operator
    response = TestClient(app).get("/api/v1/production/portfolio")

    assert response.status_code == 200
    assert response.json()["data"]["evidence"]["status"] == "UNAVAILABLE"
    assert response.json()["data"]["balances"] == []


def test_api_02_3_research_namespace_or_missing_root_fails_closed():
    for namespace, root in (("research", "D:/var/lib/indodax"), ("production_main", None)):
        try:
            create_app(
                production_namespace=namespace,
                production_state_root=root,
                venue_account_source=FakeReadOnlyIndodaxClient(),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid Production configuration was accepted")


def test_api_02_4_application_has_no_write_routes():
    methods = {
        (method, route.path)
        for route in client().app.routes
        for method in getattr(route, "methods", ())
    }
    assert {method for method, _path in methods} <= {"GET", "HEAD"}


def test_api_02_5_overview_and_mode_routes_preserve_their_resource_status():
    operator = Principal(
        subject="operator-1",
        actor_class=ActorClass.OPERATOR,
        capabilities=frozenset({Capability.PRODUCTION_READ}),
    )
    app = create_app(
        production_namespace="production_main",
        production_state_root="D:/var/lib/indodax",
        venue_account_source=FakeReadOnlyIndodaxClient(),
        mode_store=FakeModeStore(),
    )
    app.state.principal_resolver = lambda request: operator
    client = TestClient(app)

    overview = client.get("/api/v1/production/overview")
    mode = client.get("/api/v1/production/mode")

    assert overview.status_code == 200
    assert overview.json()["status"] == "PARTIAL"
    assert overview.json()["data"]["mode"] == "SHADOW"
    assert mode.status_code == 200
    assert mode.json()["status"] == "AVAILABLE"
    assert mode.json()["data"]["effective_mode"] == "SHADOW"
