#!/usr/bin/env bash
# ==============================================================================
# backup-lab.sh — Consistent research lab backup and transfer bundle creator (OPS-02)
#
# Usage: ./deploy/backup-lab.sh <source_root> <bundle_output_dir> [source_host]
# ==============================================================================

set -euo pipefail

SOURCE_ROOT="${1:-.}"
OUTPUT_DIR="${2:-./staging_bundle}"
SOURCE_HOST="${3:-asus}"

echo "[INFO] Creating consistent backup bundle from: ${SOURCE_ROOT}"
echo "[INFO] Output bundle directory: ${OUTPUT_DIR}"
echo "[INFO] Source host: ${SOURCE_HOST}"

python -c "
import sys
from pathlib import Path
from indodax_lab.operations.backup import create_backup_bundle

source = Path('${SOURCE_ROOT}').resolve()
output = Path('${OUTPUT_DIR}').resolve()
host = '${SOURCE_HOST}'

paths = []
for candidate in ['datasets', 'queue', 'experiments', 'configs']:
    p = source / candidate
    if p.exists():
        paths.append(candidate)

if not paths:
    print('[ERROR] No recognizable lab data paths found in source root!', file=sys.stderr)
    sys.exit(1)

bundle = create_backup_bundle(source, paths, output, source_host=host)
print(f'[SUCCESS] Bundle generated at {bundle}')
"

echo "[INFO] Backup completed successfully."
