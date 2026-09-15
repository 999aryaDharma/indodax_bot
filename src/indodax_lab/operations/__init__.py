"""Host operations, backup, transfer, and restore subsystem (OPS-02)."""

from indodax_lab.operations.backup import (
    backup_sqlite_db,
    compute_sha256,
    create_backup_bundle,
    is_sqlite_database,
)
from indodax_lab.operations.restore import (
    RestoreResult,
    restore_snapshot_bundle,
)
from indodax_lab.operations.staging import (
    ChecksumMismatchError,
    CorruptTransferError,
    StagingResult,
    TransferManifest,
    stage_and_publish_transfer,
    verify_bundle,
)
from indodax_lab.operations.service_lifecycle import (
    ConcurrentWriterLockError,
    HostServiceProfile,
    LifecycleOperationError,
    ManagedService,
    MissingSecretError,
    ServiceManager,
    SingleWriterLock,
)

__all__ = [
    "ChecksumMismatchError",
    "CorruptTransferError",
    "RestoreResult",
    "StagingResult",
    "TransferManifest",
    "backup_sqlite_db",
    "compute_sha256",
    "create_backup_bundle",
    "is_sqlite_database",
    "restore_snapshot_bundle",
    "stage_and_publish_transfer",
    "verify_bundle",
    # OPS-01 Service Lifecycle
    "ConcurrentWriterLockError",
    "HostServiceProfile",
    "LifecycleOperationError",
    "ManagedService",
    "MissingSecretError",
    "ServiceManager",
    "SingleWriterLock",
]
