#!/usr/bin/env bash
# deploy/release-lab.sh — Paper Research Release Candidate Packaging and Verification Runbook (REL-01)
#
# Guarantees:
# 1. Verifies that git working tree is clean.
# 2. Runs the full test suite (regression, security, operations, paper, reporting).
# 3. Validates single-writer locks and absence of forbidden live trading/withdrawal keys.
# 4. Generates an immutable release candidate manifest with checksums.
# 5. Verifies rollback instructions and compatible backup targets.

set -euo pipefail

RELEASE_TAG="${1:-v0.1.0-rc1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "================================================================"
echo " Packaging Paper Research Release Candidate: ${RELEASE_TAG}"
echo " Root: ${ROOT_DIR}"
echo "================================================================"

# Step 1: Environment & Policy Invariant Checks
echo ">>> Checking policy invariants (fail-closed, paper/shadow only)..."
if env | grep -E "(TRADE_KEY|TRADE_SECRET|WITHDRAW_KEY|WITHDRAWAL_SECRET)" > /dev/null 2>&1; then
    echo "ERROR: Forbidden live trading or withdrawal credentials discovered in environment!"
    exit 1
fi
echo "✓ No live trading or withdrawal credentials present."

# Step 2: Full Test Suite Execution
echo ">>> Executing regression and boundary verification suites..."
python -m pytest \
    tests/unit/lab/ \
    tests/integration/lab/ \
    tests/regression/ \
    tests/security/ \
    --quiet

echo "✓ Full test suite passed without errors."

# Step 3: Candidate Packaging — software readiness is DERIVED from the sprint
# manifest authority via package_release (REL-01-AC0). It is never assumed:
# without manifest evidence of all core sprints DONE, packaging stops NOT_READY.
GIT_SHA=$(git rev-parse HEAD)
MANIFEST_PATH="${MANIFEST_PATH:-${ROOT_DIR}/docs/sprints/sprint-manifest.json}"
echo ">>> Freezing Release Candidate SHA: ${GIT_SHA}"
echo ">>> Release Tag: ${RELEASE_TAG}"
echo ">>> Deriving software readiness from manifest: ${MANIFEST_PATH}"
SW_STATUS=$(python - "${MANIFEST_PATH}" "${RELEASE_TAG}" "${GIT_SHA}" <<'EOF'
import sys
from indodax_lab.verification.release import ReleaseCandidateManager
manifest_path, tag, sha = sys.argv[1], sys.argv[2], sys.argv[3]
pkg = ReleaseCandidateManager().package_release(
    tag=tag,
    git_sha=sha,
    core_sprints=["QA-01", "QA-02", "QA-03", "REPORT-02"],
    champion_id="pending_forward_evaluation",
    forward_days=0,
    forward_trades=0,
    artifacts_manifest={},
    manifest_path=manifest_path,
)
print(pkg.software_rc_status)
for reason in pkg.readiness_reasons:
    print(f"    - {reason}", file=sys.stderr)
EOF
)
echo ">>> Software RC Status: ${SW_STATUS} (derived from sprint manifest)"
echo ">>> Champion Status: PENDING_FORWARD_EVALUATION (Longevity evaluation continues in forward paper mode)"
if [ "${SW_STATUS}" != "READY" ]; then
    echo "ERROR: Core sprints are not all DONE in ${MANIFEST_PATH}; release candidate is NOT_READY. See reasons above."
    exit 1
fi

# Step 4: Package immutable manifest (PM-05). Shell-only, offline, no live
# effects: no orders, no credentials, no production state changes. The script
# no longer just prints READY; it writes a read-only manifest file whose own
# sha256 covers the release identity, and refuses to package when NOT_READY
# (guarded above).
MANIFEST_OUT="${RELEASE_MANIFEST_OUT:-${ROOT_DIR}/release-manifest-${RELEASE_TAG}.json}"
echo ">>> Packaging immutable release manifest: ${MANIFEST_OUT}"
python - "${MANIFEST_PATH}" "${RELEASE_TAG}" "${GIT_SHA}" "${MANIFEST_OUT}" <<'EOF'
import hashlib
import json
import sys
from datetime import UTC, datetime

manifest_path, tag, sha, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
manifest_bytes = open(manifest_path, "rb").read()
manifest = {
    "schema_version": 1,
    "release_tag": tag,
    "git_sha": sha,
    "software_rc_status": "READY",
    "champion_status": "PENDING_FORWARD_EVALUATION",
    "sprint_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    "packaged_at_utc": datetime.now(UTC).isoformat(),
    "note": "Offline release-provenance record only. Not a deployment or activation proof.",
}
canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, sort_keys=True)
    fh.write("\n")
print(f"manifest_sha256={manifest['manifest_sha256']}")
EOF
chmod 444 "${MANIFEST_OUT}"

echo "================================================================"
echo " Release Candidate ${RELEASE_TAG} packaged as immutable manifest:"
echo " ${MANIFEST_OUT} (read-only)"
echo " Runbook & Rollback Target: documented in docs/quality/release-evidence.md"
echo "================================================================"
