"""Secret-free audit records for Production API authorization decisions."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from indodax_lab.api.auth import ActorClass
from indodax_lab.api.capabilities import Capability

logger = logging.getLogger("indodax_lab.api.audit")
POLICY_REVISION = "api-03-policy-v1"


def record_access_decision(
    *,
    request_id: str,
    actor_class: ActorClass,
    capability: Capability,
    decision: str,
    reason: str,
) -> None:
    record = {
        "actor_class": actor_class.value,
        "capability": capability.value,
        "decision": decision,
        "reason": reason,
        "request_id": request_id,
        "resource": "production/*",
        "source_revision": POLICY_REVISION,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    logger.info(json.dumps(record, sort_keys=True, separators=(",", ":")))
