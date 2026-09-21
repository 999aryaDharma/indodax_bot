"""Production execution boundary.

This package intentionally starts with read-only venue access. Order-write capability
must live behind the OMS and must not be added to the read-only client.
"""

from indodax_lab.execution.fill_normalizer import (
    VenueFillNormalizationError,
    normalize_venue_fill,
)
from indodax_lab.execution.indodax_readonly import (
    IndodaxReadOnlyClient,
    VenueAccountSnapshot,
    VenueBalance,
    VenueFill,
    VenueOrder,
    VenueReadError,
)
from indodax_lab.execution.oms import (
    OmsOrder,
    OmsOrderState,
    OmsStateMachine,
    OmsTransitionError,
)
from indodax_lab.execution.oms_store import (
    OmsConcurrencyError,
    OmsStateCorruptionError,
    OmsStore,
)
from indodax_lab.execution.read_only_reconciler import (
    PrivateReadOnlyReconciliationService,
)
from indodax_lab.execution.reconciliation import (
    ReconciliationEngine,
    ReconciliationIssue,
    ReconciliationPolicy,
    ReconciliationReport,
    ReconciliationStatus,
)

__all__ = [
    "IndodaxReadOnlyClient",
    "OmsConcurrencyError",
    "OmsOrder",
    "OmsOrderState",
    "OmsStateCorruptionError",
    "OmsStateMachine",
    "OmsStore",
    "OmsTransitionError",
    "PrivateReadOnlyReconciliationService",
    "ReconciliationEngine",
    "ReconciliationIssue",
    "ReconciliationPolicy",
    "ReconciliationReport",
    "ReconciliationStatus",
    "VenueAccountSnapshot",
    "VenueBalance",
    "VenueFill",
    "VenueFillNormalizationError",
    "VenueOrder",
    "VenueReadError",
    "normalize_venue_fill",
]
