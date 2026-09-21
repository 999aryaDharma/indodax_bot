"""Validate architecture-program documentation without product imports or mutations."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    'DOC-01', 'RP-01', 'RP-02', 'RP-03', 'RP-04', 'RP-05',
    'RW0-01', 'RW1-01', 'RW2-01', 'RW2-02', 'RW2-03', 'RW3-01',
    'RW4-01', 'RW5-01', 'RW5-02', 'RW6-01', 'RW7-01', 'RW7-02',
    'RW8-01', 'RW8-02', 'RW9-01', 'PM-01', 'PM-02', 'PM-03',
    'PM-04', 'PM-05', 'PM-06',
}
LAYERS = ('Clock', 'Market source', 'Feature runtime', 'Candidate runtime',
          'Portfolio', 'Risk', 'OMS', 'Venue', 'Fill', 'Ledger',
          'Reconciliation', 'Metrics', 'Audit', 'Restart')
HANDOFF = ('TASK ID', 'OBJECTIVE', 'ARCHITECTURAL CONTEXT', 'ALLOWED SCOPE',
           'DO NOT TOUCH', 'PRECONDITIONS', 'IMPLEMENTATION STEPS', 'FILES',
           'TESTS', 'ACCEPTANCE CHECKS', 'EXPECTED OUTPUT', 'STOP CONDITIONS')


def validate(manifest: dict, documents: dict[str, str]) -> list[str]:
    errors = []
    rows = {row['id']: row for row in manifest['sprints']}
    if EXPECTED - rows.keys():
        errors.append('Missing program task')
    historical = [row for row in rows.values() if row.get('recovery')]
    if len(historical) != 92:
        errors.append('Legacy reconstruction count changed')
    for row in historical:
        if row['status'] == 'DONE' and row['recovery']['source_spec_status'] != 'DONE':
            # Later independent review must supply explicit new evidence, not recovery provenance.
            if row.get('evidence', {}).get('kind') != 'independent_review':
                errors.append('Unsupported recovered DONE: ' + row['id'])
    for id in EXPECTED & rows.keys():
        row = rows[id]
        text = documents.get(row['path'], '')
        if not text:
            errors.append('Missing task document: ' + id)
            continue
        if row.get('complexity') not in ('S', 'M', 'L', 'XL'):
            errors.append('Missing complexity: ' + id)
        for heading in HANDOFF:
            if '### ' + heading + '\n' not in text:
                errors.append('Missing LUNA heading: ' + id + ':' + heading)
        if not row.get('files') or not row.get('contract'):
            errors.append('Missing files/interface: ' + id)
        if re.search(r'\b(?:TBD|TODO)\b|fill in details|implement later', text):
            errors.append('Placeholder: ' + id)
        if len(row.get('acceptance_test_mapping', [])) < 4:
            errors.append('Insufficient behavior cases: ' + id)
    parity = documents.get('docs/implementation/RUNTIME-PARITY.md', '')
    for layer in LAYERS:
        if '| ' + layer + ' |' not in parity:
            errors.append('Missing parity layer: ' + layer)
    nxt = documents.get('docs/implementation/handoff/LUNA-NEXT.md', '')
    ids = re.findall(r'^## TASK ID\n\n([A-Z0-9]+-\d{2})', nxt, re.M)
    if ids != ['RP-01']:
        errors.append('Next task must be RP-01 only')
    for heading in HANDOFF:
        if '## ' + heading + '\n' not in nxt:
            errors.append('Missing next-task heading: ' + heading)
    for classification in ('IMPLEMENTED', 'PARTIAL', 'MISSING', 'LEGACY',
                           'SUPERSEDED', 'BLOCKED_EXTERNAL'):
        # Supersession classification may be defined in program README and explained in audit.
        combined = documents.get('docs/implementation/CURRENT-STATE.md', '')
        combined += documents.get('docs/implementation/README.md', '')
        if classification not in combined:
            errors.append('Missing classification: ' + classification)
    return errors


def self_test(manifest: dict, documents: dict[str, str]) -> None:
    cases = []
    changed = copy.deepcopy(manifest)
    changed['sprints'] = [r for r in changed['sprints'] if r['id'] != 'RW9-01']
    cases.append((changed, documents, 'Missing program task'))
    changed = copy.deepcopy(manifest)
    row = next(r for r in changed['sprints'] if r.get('recovery') and r['status'] == 'REVIEW')
    row['status'] = 'DONE'
    cases.append((changed, documents, 'Unsupported recovered DONE'))
    changed_docs = dict(documents)
    changed_docs['docs/implementation/RUNTIME-PARITY.md'] = ''
    cases.append((manifest, changed_docs, 'Missing parity layer'))
    changed_docs = dict(documents)
    changed_docs['docs/implementation/handoff/LUNA-NEXT.md'] = '## TASK ID\n\nRW9-01\n'
    cases.append((manifest, changed_docs, 'Next task must'))
    for changed, changed_docs, expected in cases:
        assert any(expected in e for e in validate(changed, changed_docs)), expected
    print('Program negative mutations: 4/4 rejected')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'docs/sprints/sprint-manifest.json').read_text(encoding='utf-8'))
    documents = {p.relative_to(ROOT).as_posix(): p.read_text(encoding='utf-8')
                 for p in (ROOT / 'docs').rglob('*.md')}
    errors = validate(manifest, documents)
    if errors:
        print('\n'.join(errors))
        return 1
    if args.self_test:
        self_test(manifest, documents)
    print(f'PASS: {len(EXPECTED)} program tasks, 14 parity layers, one LUNA handoff')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
