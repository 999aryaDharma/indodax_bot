#!/usr/bin/env bash
# ==============================================================================
# restore-lab.sh — Consistent research lab bundle restoration (OPS-02)
#
# Usage: ./deploy/restore-lab.sh <bundle_dir> <target_root>
# ==============================================================================

set -euo pipefail

BUNDLE_DIR="${1:-./staging_bundle}"
TARGET_ROOT="${2:-.}"

echo "[INFO] Restoring bundle from: ${BUNDLE_DIR}"
echo "[INFO] Target root directory: ${TARGET_ROOT}"

python -c "
import sys
from pathlib import Path
from indodax_lab.operations.restore import restore_snapshot_bundle

bundle = Path('${BUNDLE_DIR}').resolve()
target = Path('${TARGET_ROOT}').resolve()

if not (bundle / 'transfer_manifest.json').exists():
    print(f'[ERROR] Transfer manifest missing from bundle {bundle}!', file=sys.stderr)
    sys.exit(1)

result = restore_snapshot_bundle(bundle, target)
print(f'[SUCCESS] Restored {len(result.restored_files)} files into {result.target_root}')
"

echo "[INFO] Restore completed successfully."
