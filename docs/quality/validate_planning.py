#!/usr/bin/env python3
"""Validate documentation only. No runtime imports, network, or product mutation."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'docs/sprints/sprint-manifest.json'
STATES = {'PLANNED','BLOCKED','READY','IN_PROGRESS','REVIEW','CHANGES_REQUESTED','DONE','PAUSED','CANCELLED'}
HEADINGS = ['Metadata','Goal','Why This Sprint Exists','Depends On','Unlocks','Required Reading','Current Context','In Scope','Out of Scope','User / Actor Behavior','Functional Requirements','Domain Rules / Invariants','Architecture / Design Contract','Planned Files / Artifacts','Interfaces & Contracts','Data / Persistence Impact','API / External Contract Impact','UI / UX Behavior','Implementation Steps','Required Tests','Failure / Edge Cases','Security / Privacy / Safety','Concurrency / Idempotency','Performance Constraints','Observability','Migration / Backward Compatibility','Rollback / Recovery','Acceptance Criteria','Definition of Done','Reviewer Checklist','Commit Guidance','Handoff Requirements','Ready-to-Run Implementation Prompt']
WORKFLOWS = ['start-project','next-sprint','implement-sprint','review-sprint','fix-review','re-review','debug-bug','change-request','security-audit','performance-audit','parallel-plan','two-agent-handoff','pre-merge','release-check']

def validate(m, root=ROOT):
    errors=[]; rows=m.get('sprints',[]); ids=[s['id'] for s in rows]; by={s['id']:s for s in rows}
    if len(ids)!=len(set(ids)): errors.append('Duplicate sprint IDs')
    paths=[s['path'] for s in rows]
    if len(paths)!=len(set(paths)): errors.append('Duplicate sprint paths')
    color={}; depth={}
    def visit(id):
        if color.get(id)==1: raise ValueError('Dependency cycle: '+id)
        if color.get(id)==2:return depth[id]
        color[id]=1
        depth[id]=max((visit(d)+1 for d in by[id]['dependencies'] if d in by),default=0)
        color[id]=2;return depth[id]
    for id in by:
        try:visit(id)
        except ValueError as e:errors.append(str(e));break
    for s in rows:
        id=s['id']; path=root/s['path']; deps=s['dependencies']
        if not re.fullmatch(r'[A-Z][A-Z0-9]*-\d{2}',id):errors.append(id+': Invalid ID')
        if len(deps)!=len(set(deps)):errors.append(id+': Duplicate dependency')
        if not all(d in by for d in deps):errors.append(id+': Unknown dependency')
        if s['status'] not in STATES:errors.append(id+': Invalid status')
        if s['status']=='READY' and not all(d in by and by[d]['status']=='DONE' for d in deps):errors.append(id+': Premature READY')
        if s['status']=='PLANNED' and all(d in by and by[d]['status']=='DONE' for d in deps):errors.append(id+': Eligible PLANNED must be READY or explicitly BLOCKED/PAUSED')
        expected=[t['id'] for t in rows if id in t['dependencies']]
        if s.get('unlocks')!=expected:errors.append(id+': Unlock projection mismatch')
        if not path.is_file():errors.append(id+': Missing sprint file');continue
        if path.parent.name!=s['domain']:errors.append(id+': Wrong domain folder')
        text=path.read_text(encoding="utf-8"); headings=re.findall(r'^## (.+)$',text,re.M)
        for h in HEADINGS:
            if h not in headings:errors.append(id+': Missing heading '+h)
            elif not re.search(r'^## '+re.escape(h)+r'\n\n\S',text,re.M):errors.append(id+': Empty heading '+h)
        if f'Status: {s["status"]}\n' not in text:errors.append(id+': Status metadata mismatch')
        required=text.split('## Required Reading\n',1)[-1].split('\n## ',1)[0]
        actual=re.findall(r'`([^`]+)`',required)
        if actual!=s['required_reading']:errors.append(id+': Reading list mismatch')
        for p in s['required_reading']:
            if not (root/p).is_file():errors.append(id+': Missing Required Reading '+p)
        if not s.get('requirements'):errors.append(id+': Missing FR mapping')
        for r in s.get('requirements',[]):
            if r not in (root/'docs/specs/00-master-product-technical-spec.md').read_text(encoding="utf-8"):errors.append(id+': Unknown requirement '+r)
        if len(s.get('acceptance_test_mapping',[]))<3:errors.append(id+': Missing behavior-test mapping')
        for ac in s.get('acceptance_test_mapping',[]):
            if ac['criterion'] not in text or ac['behavior'] not in text:errors.append(id+': AC mapping missing from spec')
        if s['status']=='DONE':
            e=s.get('evidence')
            if not e or not (root/e['path']).is_file():errors.append(id+': DONE without evidence')
            if not (root/f'docs/sprints/handoffs/{id}-HANDOFF.md').is_file():errors.append(id+': DONE without handoff')
    mapped={t for s in rows for t in s['legacy_tasks']}
    if mapped!=set(range(1,36)):errors.append('Legacy task coverage must include 1..35 exactly')
    for wf in WORKFLOWS:
        if not (root/f'.agents/workflows/{wf}.md').is_file():errors.append('Missing workflow '+wf)
    # Every owned sprint file must belong to manifest; handoffs/index documents are excluded.
    for domain in {s['domain'] for s in rows}:
        for file in (root/'docs/sprints'/domain).glob('*.md'):
            if file.relative_to(root).as_posix() not in paths:errors.append('Unreferenced sprint '+str(file))
    # Validate local Markdown links in the newly governed documentation surface.
    docfiles=[root/'AGENTS.md',root/'docs/README.md']
    for folder in ['.agents','docs/specs','docs/sprints','docs/agent','docs/templates','docs/decisions','docs/quality','docs/runbooks','docs/implementation','docs/production']:
        docfiles.extend((root/folder).rglob('*.md'))
    for file in docfiles:
        if not file.exists():errors.append('Missing documentation '+str(file));continue
        text=file.read_text(encoding="utf-8")
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in target or target.startswith(('#','mailto:')):continue
            clean=target.split('#',1)[0]
            if clean and not (file.parent/clean).exists():errors.append(str(file.relative_to(root))+': Broken link '+target)
    return errors,depth

def refresh(m):
    rows=m['sprints']; by={s['id']:s for s in rows}
    for s in rows:
        if s['status'] in ('READY','PLANNED'):
            s['status']='READY' if all(by[d]['status']=='DONE' for d in s['dependencies']) else 'PLANNED'
        s['unlocks']=[t['id'] for t in rows if s['id'] in t['dependencies']]
        path=ROOT/s['path']
        text=path.read_text(encoding="utf-8")
        text=re.sub(r'^Status: \w+$','Status: '+s['status'],text,count=1,flags=re.M)
        text=re.sub(r'(?<=## Depends On\n\n).*?(?=\n\n## Unlocks)', '\n'.join('- '+d+' — '+by[d]['title'] for d in s['dependencies']) or 'None. This capability can establish its own offline acceptance fixture.',text,flags=re.S)
        text=re.sub(r'(?<=## Unlocks\n\n).*?(?=\n\n## Required Reading)', ', '.join(s['unlocks']) or 'No mandatory dependent sprint.',text,flags=re.S)
        path.write_text(text.rstrip()+'\n', encoding="utf-8")
    (ROOT/MANIFEST).write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n', encoding="utf-8")
    _,depth=validate(m)
    def put(p,text):(ROOT/p).write_text(text.strip()+'\n', encoding="utf-8")
    ready=[s['id'] for s in rows if s['status']=='READY']
    put('docs/sprints/STATUS-SUMMARY.md','# Current status summary\n\nDerived from manifest; historical baseline is retained separately.\n\n'+str(dict(Counter(s['status'] for s in rows)))+'\n\nREADY: '+', '.join(ready)+'.\n')
    index=['# Sprint index','Derived from manifest. Historical DONE does not imply fresh test execution.','| ID | Feature | Domain | Priority | Type | Dependencies | State | Path |','|---|---|---|---|---|---|---|---|']
    for s in rows:index.append(f"| {s['id']} | {s['title']} | {s['domain']} | {s['priority']} | {s['type']} | {', '.join(s['dependencies']) or '—'} | {s['status']} | [Spec]({os.path.relpath(s['path'],'docs/sprints')}) |")
    put('docs/sprints/00-sprint-index.md','\n'.join(index))
    wavefile=ROOT/'docs/sprints/02-execution-waves.md'
    pre=wavefile.read_text(encoding="utf-8").split('## Wave 0',1)[0]
    pre=re.sub(r'(?<=## Computed initial queue\n\n).*?(?=\n\n)',', '.join(ready)+'. Verify external gates and shared-file ownership before claim.',pre,count=1,flags=re.S)
    waves=[pre.strip()]
    for level in sorted(set(depth.values())):
        waves+=['## Wave '+str(level),'\n'.join('- '+s['id']+' — '+s['title']+' ['+s['status']+'; '+s['tier']+']' for s in rows if depth[s['id']]==level)]
    put('docs/sprints/02-execution-waves.md','\n\n'.join(waves))
    fmap=['# Feature map','CORE is initial paper/research scope; EXTENSION/EXPERIMENTAL require owner activation.']
    for domain in dict.fromkeys(s['domain'] for s in rows):
        fmap+=['## '+domain,'\n'.join(f"- [{s['id']} — {s['title']}]({os.path.relpath(s['path'],'docs/sprints')}) — {s['tier']}; {s['goal']}" for s in rows if s['domain']==domain)]
    put('docs/sprints/FEATURE-MAP.md','\n\n'.join(fmap))
    graphpath=ROOT/'docs/sprints/01-dependency-graph.md'
    tail=graphpath.read_text(encoding="utf-8").split('## Selected critical boundaries',1)[1]
    tail=re.sub(r'Nodes: \d+\. Edges: \d+\.',f"Nodes: {len(rows)}. Edges: {sum(len(s['dependencies']) for s in rows)}.",tail)
    graph=['# Dependency graph','Full edge list; prerequisite → consumer. Manifest is authoritative.','| Consumer | Direct prerequisites |','|---|---|']
    graph+=['| '+s['id']+' | '+(', '.join(s['dependencies']) or 'None')+' |' for s in rows]
    put('docs/sprints/01-dependency-graph.md','\n'.join(graph)+'\n\n## Selected critical boundaries'+tail)
    tracepath=ROOT/'docs/quality/requirements-traceability.md'
    tail=tracepath.read_text(encoding="utf-8").split('| Non-functional requirement',1)[1]
    trace=['# Requirements traceability','AC behavior-test mappings and evidence references are in manifest/sprint handoffs.','| Requirement | Domain | Sprints | Evidence owner |','|---|---|---|---|']
    for domain in dict.fromkeys(s['domain'] for s in rows):
        ss=[s for s in rows if s['domain']==domain]
        trace.append('| '+', '.join(sorted({r for s in ss for r in s['requirements']}))+' | '+domain+' | '+', '.join(s['id'] for s in ss)+' | Sprint handoff / historical evidence |')
    put('docs/quality/requirements-traceability.md','\n'.join(trace)+'\n\n| Non-functional requirement'+tail)

def self_test(m):
    mutations=[]
    x=copy.deepcopy(m);x['sprints'].append(copy.deepcopy(x['sprints'][0]));mutations.append(('duplicate ID',x,'Duplicate sprint IDs'))
    x=copy.deepcopy(m);x['sprints'][0]['dependencies']=['DOES-NOT-EXIST'];mutations.append(('unknown dependency',x,'Unknown dependency'))
    x=copy.deepcopy(m);x['sprints'][0]['dependencies']=[x['sprints'][0]['id']];mutations.append(('cycle',x,'Dependency cycle'))
    x=copy.deepcopy(m);x['sprints'][0]['path']='docs/sprints/missing.md';mutations.append(('missing file',x,'Missing sprint file'))
    x=copy.deepcopy(m);x['sprints'][0]['status']='READY';x['sprints'][0]['dependencies']=[x['sprints'][0]['id']];mutations.append(('premature READY',x,'Premature READY'))
    x=copy.deepcopy(m);x['sprints'][0]['required_reading'].append('nonexistent-spec.md');mutations.append(('missing reading',x,'Missing Required Reading'))
    x=copy.deepcopy(m);x['sprints'][0]['status']='DONE';x['sprints'][0]['evidence']=None;mutations.append(('false DONE',x,'DONE without evidence'))
    for name,x,expected in mutations:
        errors,_=validate(x)
        if not any(expected in e for e in errors):raise AssertionError('Mutation escaped: '+name)
    print('Validator negative mutations: 7/7 rejected')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args();m=json.loads((ROOT/MANIFEST).read_text(encoding="utf-8"))
    if args.refresh:refresh(m)
    errors,depth=validate(m)
    if errors:
        print('\n'.join(errors));return 1
    if args.self_test:self_test(m)
    print(json.dumps({'result':'PASS','nodes':len(m['sprints']),'edges':sum(len(s['dependencies']) for s in m['sprints']),'cycles':0,'domains':len({s['domain'] for s in m['sprints']}),'headings_per_sprint':len(HEADINGS),'ready':[s['id'] for s in m['sprints'] if s['status']=='READY'],'states':dict(Counter(s['status'] for s in m['sprints'])),'maximum_dependency_depth':max(depth.values())},indent=2))
    return 0
if __name__=='__main__':sys.exit(main())
