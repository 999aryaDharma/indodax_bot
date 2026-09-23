from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from indodax_lab.api.capabilities import DEVELOPMENT_DENIED_CAPABILITIES, Capability
from indodax_lab.api.contracts.common import (
    ApiEnvelope,
    ApiError,
    IdempotencyKey,
    Provenance,
    RequestContext,
)


def test_api_00_0_rejects_naive_as_of_and_normalizes_aware_timestamp() -> None:
    provenance = Provenance(source="oms", revision="rev-1")

    with pytest.raises(ValidationError):
        ApiEnvelope(
            request_id="req-1",
            as_of=datetime(2026, 9, 23),
            source_revision="rev-1",
            status="AVAILABLE",
            data={},
            provenance=provenance,
        )

    value = ApiEnvelope(
        request_id="req-1",
        as_of=datetime(2026, 9, 23, 8, tzinfo=timezone(timedelta(hours=8))),
        source_revision="rev-1",
        status="AVAILABLE",
        data={"equity": Decimal("12.30")},
        provenance=provenance,
    )
    assert value.as_of == datetime(2026, 9, 23, tzinfo=UTC)
    assert value.model_dump_json() == (
        '{"request_id":"req-1","as_of":"2026-09-23T00:00:00Z",'
        '"source_revision":"rev-1","status":"AVAILABLE",'
        '"data":{"equity":"12.30"},"provenance":{"source":"oms",'
        '"revision":"rev-1"}}'
    )


def test_api_00_1_rejects_non_finite_decimal_and_serializes_finite_decimal_as_string() -> None:
    envelope = ApiEnvelope(
        request_id="req-1",
        as_of=datetime(2026, 9, 23, tzinfo=UTC),
        source_revision="rev-1",
        status="AVAILABLE",
        data={"equity": Decimal("12.30")},
        provenance=Provenance(source="ledger", revision="rev-1"),
    )
    assert '"equity":"12.30"' in envelope.model_dump_json()

    with pytest.raises(ValidationError):
        ApiEnvelope(
            request_id="req-1",
            as_of=datetime(2026, 9, 23, tzinfo=UTC),
            source_revision="rev-1",
            status="AVAILABLE",
            data={"equity": Decimal("NaN")},
            provenance=Provenance(source="ledger", revision="rev-1"),
        )


def test_api_00_2_rejects_unknown_capabilities_and_malformed_envelopes() -> None:
    assert Capability("production.read") is Capability.PRODUCTION_READ
    with pytest.raises(ValueError):
        Capability("production.superuser")

    with pytest.raises(ValidationError):
        ApiEnvelope.model_validate(
            {
                "request_id": "req-1",
                "as_of": "2026-09-23T00:00:00Z",
                "source_revision": "rev-1",
                "status": "AVAILABLE",
                "data": {},
                "provenance": {"source": "oms", "revision": "rev-1"},
                "unexpected": True,
            }
        )
    with pytest.raises(ValidationError):
        ApiEnvelope.model_validate(
            {
                "request_id": "req-1",
                "as_of": "2026-09-23T00:00:00Z",
                "source_revision": "rev-1",
                "status": "READY",
                "data": {},
                "provenance": {"source": "oms", "revision": "rev-1"},
            }
        )

    context = RequestContext(
        request_id="req-2", actor=None, capabilities={Capability.PRODUCTION_READ}
    )
    assert context.capabilities == frozenset({Capability.PRODUCTION_READ})
    assert DEVELOPMENT_DENIED_CAPABILITIES == frozenset({Capability.PRODUCTION_WRITE})
    with pytest.raises(ValidationError):
        RequestContext.model_validate(
            {"request_id": "req-2", "capabilities": ["production.superuser"]}
        )

    assert ApiError(
        code="SOURCE_UNAVAILABLE", message="Source unavailable", retryable=True
    ).model_dump() == {
        "code": "SOURCE_UNAVAILABLE",
        "message": "Source unavailable",
        "retryable": True,
        "details": None,
    }
    with pytest.raises(ValidationError):
        ApiError(
            code="SOURCE_UNAVAILABLE",
            message="Source unavailable",
            retryable=True,
            details={"measurement": [Decimal("NaN")]},
        )
    assert IdempotencyKey(value=" key-1 ").value == "key-1"
