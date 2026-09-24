from fastapi import Request

from indodax_lab.api.auth import ActorClass, tailscale_principal_resolver
from indodax_lab.api.capabilities import Capability


def _request(login: str | None, client_host: str) -> Request:
    headers = [] if login is None else [(b"tailscale-user-login", login.encode())]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (client_host, 1234),
            "server": ("127.0.0.1", 8000),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_api_07_0_exact_allowlisted_loopback_identity_gets_read_only_capability() -> None:
    resolve = tailscale_principal_resolver({"arya@example.com"})

    principal = resolve(_request("Arya@Example.com", "127.0.0.1"))

    assert principal is not None
    assert principal.subject == "arya@example.com"
    assert principal.actor_class is ActorClass.OPERATOR
    assert principal.capabilities == {Capability.PRODUCTION_READ}


def test_api_07_1_missing_disallowed_and_nonloopback_identities_are_denied() -> None:
    resolve = tailscale_principal_resolver({"arya@example.com"})

    assert resolve(_request(None, "127.0.0.1")) is None
    assert resolve(_request("other@example.com", "127.0.0.1")) is None
    assert resolve(_request("arya@example.com", "100.64.0.2")) is None
    assert resolve(_request("arya@example.com", "not-an-ip")) is None
