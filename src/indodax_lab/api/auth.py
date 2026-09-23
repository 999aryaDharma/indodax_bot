"""Explicit identity boundary for the versioned API."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from indodax_lab.api.capabilities import Capability

_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


class ActorClass(StrEnum):
    OPERATOR = "operator"
    SERVICE = "service"
    RESEARCH = "research"
    ANONYMOUS = "anonymous"


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(min_length=1)
    actor_class: ActorClass
    capabilities: frozenset[Capability] = frozenset()


class PolicyContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    actor_class: ActorClass
    capability: Capability
    as_of: datetime


def ensure_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id
    header = request.headers.get("x-request-id", "")
    request_id = header if _REQUEST_ID_PATTERN.fullmatch(header) else str(uuid4())
    request.state.request_id = request_id
    return request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        ensure_request_id(request)
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response
