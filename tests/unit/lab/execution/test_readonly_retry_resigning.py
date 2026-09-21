"""Unit tests verifying IndodaxReadOnlyClient generates fresh timestamps
and HMAC signatures on retries.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from indodax_lab.execution.indodax_readonly import IndodaxReadOnlyClient


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def request(self, method: str, url: str, *, headers: dict, data: str | None, timeout: float):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def test_legacy_view_call_regenerates_timestamp_and_signature_on_retry() -> None:
    # First attempt returns 500 retryable error; second attempt succeeds
    session = FakeSession(
        [
            FakeResponse({"error": "server_error"}, status_code=500),
            FakeResponse(
                {
                    "success": 1,
                    "return": {
                        "server_time": 1_726_000_000,
                        "balance": {"idr": "1000000"},
                        "balance_hold": {"idr": "0"},
                    },
                },
                status_code=200,
            ),
        ]
    )

    ticking_timestamps = [1_700_000_000_000, 1_700_000_001_500]

    def clock_fn() -> int:
        return ticking_timestamps.pop(0)

    client = IndodaxReadOnlyClient(
        api_key="view-key-1",
        secret_key="secret-key-1",
        session=session,
        clock_ms=clock_fn,
        sleep_fn=lambda _: None,
        max_attempts=2,
    )

    client.get_account_snapshot()

    assert len(session.calls) == 2

    call_1 = session.calls[0]
    call_2 = session.calls[1]

    # Timestamp in attempt 1 must be 1700000000000
    params_1 = parse_qs(call_1["data"])
    assert params_1["timestamp"][0] == "1700000000000"

    # Timestamp in attempt 2 must be 1700000001500
    params_2 = parse_qs(call_2["data"])
    assert params_2["timestamp"][0] == "1700000001500"

    # Signature in attempt 2 must be different from attempt 1
    assert call_1["headers"]["Sign"] != call_2["headers"]["Sign"]


def test_v2_get_regenerates_timestamp_and_signature_on_retry() -> None:
    # First attempt returns 429 rate limited; second attempt succeeds
    session = FakeSession(
        [
            FakeResponse({"error": "too_many_requests"}, status_code=429),
            FakeResponse(
                {"data": []},
                status_code=200,
            ),
        ]
    )

    ticking_timestamps = [1_700_000_100_000, 1_700_000_102_000]

    def clock_fn() -> int:
        return ticking_timestamps.pop(0)

    client = IndodaxReadOnlyClient(
        api_key="view-key-2",
        secret_key="secret-key-2",
        session=session,
        clock_ms=clock_fn,
        sleep_fn=lambda _: None,
        max_attempts=2,
    )

    client.get_trade_fills(pair="btc_idr")

    assert len(session.calls) == 2

    call_1 = session.calls[0]
    call_2 = session.calls[1]

    # Query strings must have distinct timestamps
    query_1 = parse_qs(urlparse(call_1["url"]).query)
    query_2 = parse_qs(urlparse(call_2["url"]).query)

    assert query_1["timestamp"][0] == "1700000100000"
    assert query_2["timestamp"][0] == "1700000102000"
    assert call_1["headers"]["Sign"] != call_2["headers"]["Sign"]
