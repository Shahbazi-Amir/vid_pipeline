"""Small isolated persistence bridge over the frozen existing validator.

No semantic decisions, model APIs, full ledger copies or automatic packaging.
Workers write immutable delta batches and a small pointer under their own path.
Existing incremental_review validation/merge is reused in memory only.
"""
import argparse
import copy
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PARALLEL = Path(__file__).resolve().parents[1]
RECOVERY = PARALLEL.parent
sys.path.insert(0,str(RECOVERY))
import incremental_review as frozen
from audit_structure import rows,sha,canonical,save,validate_schema

def assignment(worker):
    plan=json.loads((PARALLEL/'PLAN.json').read_text())
    entry=next(e for e in plan['workers'] if e['owner']==worker)
    path=PARALLEL/entry['assignment_path']
    assert sha(path.read_bytes())==entry['assignment_sha256'], 'assignment changed'
    a=json.loads(path.read_text())
    for n,h in plan['frozen_files'].items():
        assert sha((RECOVERY/n).read_bytes())==h, 'frozen baseline/tool changed: '+n
    for n,h in plan['shared_files'].items():
        assert sha((PARALLEL/n).read_bytes())==h, 'shared contract changed: '+n
    assert len(a['candidates'])==378
    assert [r['position'] for r in a['candidates']]==list(range(a['positions'][0],a['positions'][1]+1))
    assert len({r['candidate_id'] for r in a['candidates']})==378
    return a

def sources(a,work):
    plan=json.loads((PARALLEL/'PLAN.json').read_text());loaded=[]
    for name in ['inputs.jsonl','outputs.jsonl']:
        h=plan['aggregate_hashes'][name]
        path=work/'source_cache'/name
        if not path.exists():path=RECOVERY/name
        assert path.exists(), 'Rebuild fixed sources in your own source_cache first: '+name
        assert sha(path.read_bytes())==h, 'fixed source hash mismatch'
        loaded.append(rows(path))
    inputs,outputs=loaded
    for r in a['candidates']:
        i,o=inputs[r['position']-1],outputs[r['position']-1]
        assert i['candidate_id']==o['candidate_id']==r['candidate_id']
        assert i['messages_sha256']==r['messages_sha256']
        assert o['response_sha256']==r['original_response_sha256']
    return inputs,outputs

def baseline():
    plan=json.loads((PARALLEL/'PLAN.json').read_text())
    return frozen.load(RECOVERY/plan['baseline_snapshot_path'])

def strict_decision(d,a,inputs,outputs):
    schema=json.loads((PARALLEL/'shared/decision.schema.json').read_text())
    validate_schema(d,schema)
    audit,support=d['audit'],d['support'];cid=audit['candidate_id']
    owned={r['candidate_id']:r for r in a['candidates']}
    assert cid in owned, 'candidate outside assignment'
    assert audit['position']==owned[cid]['position']
    assert support['candidate_id']==cid
    assert audit['schema_version']==support['schema_version']==2
    assert type(audit['revision']) is int and type(support['revision']) is int
    assert not support['independent'] and not audit['context_independence']
    payload=json.loads(inputs[audit['position']-1]['messages'][1]['content'])
    assert audit['evidence_text_hashes']==[sha(e['text'].encode()) for e in payload['evidence']]
    assert audit['independent_semantic_entailment']==support['independent_semantic_entailment']=='NOT_EVALUATED'
    if 'repair' in d:
        repair=d['repair'];assert repair['candidate_id']==cid
        assert repair['position']==audit['position'] and repair['revision']==audit['revision']
        assert repair['method']=='AGENT_REVIEW' and repair['gold_used'] is False
        assert repair['rechecked'] is True and repair['recheck_reason_fa'] and repair['reason_fa']
        assert repair['revised_response_sha256']!=repair['previous_response_sha256']
        assert repair['revised_response_sha256']==audit['response_sha256']
    for cr in support['claim_results']:
        assert cr['method']=='AGENT_REVIEW'
        assert cr['outcome'] in {'SUPPORTED','UNSUPPORTED','PARTIAL','UNRESOLVED'}
        for sp in cr['supporting_spans']:
            assert sp['unit']=='UNICODE_CODE_POINT' and sp['semantic_reason_fa']
    for u in support['answer_units']:
        assert u['kind'] in {'FACTUAL','EVIDENCE_LIMITATION','ABSTENTION','INTERPRETIVE'}
        assert type(u['claim_indices']) is list
    if audit['status']=='REPAIRED':assert audit['revision']>0
    if audit['status']=='KEEP':assert audit['revision']==0
    if audit['status']=='REVIEW_REQUIRED':assert audit['reason_fa'] and audit['error_categories']

def apply(state,decisions,a,inputs,outputs):
    assert len({d['audit']['candidate_id'] for d in decisions})==len(decisions), 'duplicate in batch'
    for d in decisions:strict_decision(d,a,inputs,outputs)
    previous=frozen.source_rows
    try:
        # Only inject read-only source rows into the frozen merge function.
        frozen.source_rows=lambda:(inputs,outputs)
        state=frozen.append_decisions(copy.deepcopy(state),decisions)
    finally:frozen.source_rows=previous
    return state

def statistics(a,state):
    owned={r['candidate_id'] for r in a['candidates']}
    audited={r['candidate_id']:r for r in state['audit.jsonl'] if r['candidate_id'] in owned}
    counts=Counter(r['status'] for r in audited.values())
    return dict(reviewed=len(audited),pending=378-len(audited),status_counts=dict(counts),
                completed_candidate_ids=sorted(audited),
                next_position=next((r['position'] for r in a['candidates'] if r['candidate_id'] not in audited),None),
                assignment_complete=len(audited)==378,import_ready=False)

def load_worker(a,work,inputs,outputs,pointer=None):
    state=baseline();pointer=pointer or work/'CURRENT.json'
    if not pointer.exists():return state,dict(batches=[])
    current=json.loads(pointer.read_text())
    assert current['owner']==a['owner'] and current['run_id']==a['run_id']
    assert current['assignment_sha256']==sha((PARALLEL/'assignments'/f"{a['owner']}.json").read_bytes())
    seen=[]
    for ref in current['batches']:
        assert re.fullmatch(r'batches/batch_[0-9]{4}/checkpoint.json',ref['path'])
        checkpoint=work/ref['path'];assert sha(checkpoint.read_bytes())==ref['sha256']
        cp=json.loads(checkpoint.read_text());directory=checkpoint.parent
        assert cp['owner']==a['owner'] and cp['run_id']==a['run_id']
        assert cp['assignment_sha256']==current['assignment_sha256']
        assert cp['previous_batches']==seen, 'checkpoint lineage changed'
        assert set(cp['files'])=={'audit.jsonl','support.jsonl','repairs.jsonl','ledger.jsonl','review_queue.jsonl','validation.json'}
        for n,h in cp['files'].items():assert sha((directory/n).read_bytes())==h,n
        audits=rows(directory/'audit.jsonl');supports=rows(directory/'support.jsonl');repairs=rows(directory/'repairs.jsonl')
        ai=frozen.index(audits);si=frozen.index(supports);ri=frozen.index(repairs)
        assert set(ai)==set(si) and set(ri)<=set(ai)
        decisions=[dict(audit=r,support=si[r['candidate_id']],**({'repair':ri[r['candidate_id']]} if r['candidate_id'] in ri else {})) for r in audits]
        state=apply(state,decisions,a,inputs,outputs)
        expected=[r for r in state['candidate_ledger.jsonl'] if r['candidate_id'] in ai]
        assert rows(directory/'ledger.jsonl')==expected
        assert rows(directory/'review_queue.jsonl')==[r for r in audits if r['status']=='REVIEW_REQUIRED']
        assert cp['candidate_ids']==list(ai)
        assert json.loads((directory/'validation.json').read_text())['statistics']==statistics(a,state)
        seen.append(ref)
    assert {k:current[k] for k in statistics(a,state)}==statistics(a,state)
    frozen.validate(state,inputs,outputs)
    return state,current

def commit_batch(a,work,inputs,outputs,decisions,batch):
    assert re.fullmatch(r'batch_[0-9]{4}',batch)
    assert 1<=len(decisions)<=10, 'Use small explicit review groups'
    state,current=load_worker(a,work,inputs,outputs)
    before=statistics(a,state);changed=apply(state,decisions,a,inputs,outputs)
    after=statistics(a,changed)
    if changed==state:return current  # Exact re-run has no file writes.
    assert after['reviewed']>=before['reviewed']
    directory=work/'batches'/batch;assert not directory.exists(), 'immutable batch exists'
    assert batch==f"batch_{len(current['batches'])+1:04d}", 'nonsequential checkpoint'
    temp=directory.with_name(batch+'.staging');temp.mkdir(parents=True,exist_ok=False)
    audits=[d['audit'] for d in decisions];cids={r['candidate_id'] for r in audits}
    data={'audit.jsonl':audits,'support.jsonl':[d['support'] for d in decisions],
          'repairs.jsonl':[d['repair'] for d in decisions if 'repair' in d],
          'ledger.jsonl':[r for r in changed['candidate_ledger.jsonl'] if r['candidate_id'] in cids],
          'review_queue.jsonl':[r for r in audits if r['status']=='REVIEW_REQUIRED']}
    for n,v in data.items():save(temp/n,v,True)
    save(temp/'validation.json',dict(statistics=after,validator='frozen incremental_review.validate',
         semantic_method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner=a['owner'],run_id=a['run_id'],assignment_sha256=sha((PARALLEL/'assignments'/f"{a['owner']}.json").read_bytes()),
            previous_batches=current['batches'],candidate_ids=[r['candidate_id'] for r in audits],
            files={n:sha((temp/n).read_bytes()) for n in [*data,'validation.json']},
            created_utc=datetime.now(timezone.utc).isoformat())
    save(temp/'checkpoint.json',cp)
    for n,h in cp['files'].items():assert sha((temp/n).read_bytes())==h
    os.replace(temp,directory)
    pointer=dict(owner=a['owner'],run_id=a['run_id'],assignment_sha256=cp['assignment_sha256'],
                 batches=current['batches']+[{'path':f'batches/{batch}/checkpoint.json','sha256':sha((directory/'checkpoint.json').read_bytes())}],**after)
    # Validate/reload the staged pointer before the atomic publication.
    testpointer=work/'CURRENT.pending.json';save(testpointer,pointer)
    oldpointer=work/'CURRENT.json'
    load_worker(a,work,inputs,outputs,pointer=testpointer)
    os.replace(testpointer,oldpointer);load_worker(a,work,inputs,outputs)
    (work/'PROGRESS_FA.md').write_text(f"بررسی‌شده: {after['reviewed']} از ۳۷۸؛ باقی‌مانده: {after['pending']}\nادامه از position: {after['next_position']}\nروش: AGENT_REVIEW؛ import-ready: false\n")
    return pointer

def rebuild_sources(work):
    deps=json.loads((RECOVERY/'DEPENDENCIES.json').read_text());repo=RECOVERY.parents[2]
    cache=work/'source_cache';cache.mkdir(parents=True,exist_ok=True)
    for kind in ['inputs','outputs']:
        records=[]
        for item in deps['fixed_batch_files']:
            if item['kind']!=kind:continue
            path=repo/item['repository_path'];assert sha(path.read_bytes())==item['sha256']
            records.extend(rows(path))
        content=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in records).encode()
        assert sha(content)==deps['aggregates'][kind+'.jsonl']['sha256']
        save(cache/(kind+'.jsonl'),records,True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['rebuild-sources','verify','commit-batch','recover-pending'])
    parser.add_argument('--worker',required=True);parser.add_argument('--directory',type=Path)
    parser.add_argument('--decisions',type=Path);parser.add_argument('--batch')
    args=parser.parse_args();a=assignment(args.worker)
    repo=RECOVERY.parents[2];work=repo/a['output_path']
    if args.directory:
        assert args.action=='verify', 'alternate path is read-only verification only'
        work=args.directory.resolve()
    if args.action=='rebuild-sources':rebuild_sources(work);return
    inputs,outputs=sources(a,work)
    if args.action=='recover-pending':
        prior_state,prior=load_worker(a,work,inputs,outputs)
        pending=work/'CURRENT.pending.json'
        if not pending.exists():
            batch=f"batch_{len(prior['batches'])+1:04d}"
            checkpoint=work/'batches'/batch/'checkpoint.json'
            cp=json.loads(checkpoint.read_text())
            assert cp['previous_batches']==prior['batches']
            stats=json.loads((checkpoint.parent/'validation.json').read_text())['statistics']
            save(pending,dict(owner=a['owner'],run_id=a['run_id'],assignment_sha256=cp['assignment_sha256'],
                batches=prior['batches']+[dict(path=f'batches/{batch}/checkpoint.json',sha256=sha(checkpoint.read_bytes()))],**stats))
        new_state,pointer=load_worker(a,work,inputs,outputs,pointer=pending)
        assert pointer['batches'][:-1]==prior['batches'], 'pending pointer is not the next generation'
        os.replace(pending,work/'CURRENT.json')
    elif args.action=='commit-batch':
        assert args.decisions and args.batch
        pointer=commit_batch(a,work,inputs,outputs,rows(args.decisions),args.batch)
    else:
        state,pointer=load_worker(a,work,inputs,outputs);pointer=statistics(a,state)
    print(json.dumps(pointer,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
