"""Storage-only synthetic fixtures; never evidence of a semantic review."""
import copy
import json
import tempfile
from pathlib import Path
from range_io import assignment,sources,baseline,apply,statistics,commit_batch,load_worker,RECOVERY,PARALLEL
from audit_structure import canonical,sha

def run():
    plan=json.loads((PARALLEL/'PLAN.json').read_text())
    assignments=[assignment(f'auditor_{k}') for k in [1,2,3]]
    all_rows=[r for a in assignments for r in a['candidates']]
    assert len(all_rows)==len({r['candidate_id'] for r in all_rows})==1134
    assert [r['position'] for r in all_rows]==list(range(16,1150))
    before={n:sha((RECOVERY/n).read_bytes()) for n in ['checkpoints/CURRENT.json','candidate_ledger.jsonl','audit.jsonl','support.jsonl','repairs.jsonl','outputs.jsonl']}
    a=assignments[0];inputs,outputs=sources(a,PARALLEL/'workers/auditor_1')
    pos=16;inp,out=inputs[pos-1],outputs[pos-1];payload=json.loads(inp['messages'][1]['content'])
    reason='TEST_FIXTURE_ONLY: synthetic unresolved record; not a real semantic review'
    audit=dict(schema_version=2,candidate_id=inp['candidate_id'],position=pos,revision=0,
        response_sha256=out['response_sha256'],status='REVIEW_REQUIRED',method='AGENT_REVIEW',
        context_independence=False,full_evidence_reviewed=True,evidence_ids_reviewed=[e['evidence_id'] for e in payload['evidence']],
        evidence_text_hashes=[sha(e['text'].encode()) for e in payload['evidence']],
        dimensions={k:'TEST_UNRESOLVED' for k in ['evidence_sufficiency','question_answer_fit','factual_claim_support','scope_modality_negation_quantity','outside_details','abstention_justified','ambiguity_conflict']},
        reason_fa=reason,error_categories=['TEST_FIXTURE_ONLY'],gold_used_for_review=False,
        answer_factual_coverage_reviewed=True,independent_semantic_entailment='NOT_EVALUATED')
    claims=out['response']['claims']
    support=dict(schema_version=2,candidate_id=inp['candidate_id'],response_sha256=out['response_sha256'],revision=0,
        method='AGENT_REVIEW',independent=False,claim_results=[dict(claim_index=k,claim_sha256=canonical(cl),claim_text=cl['claim_text'],
        evidence_ids=cl['evidence_ids'],outcome='UNRESOLVED',method='AGENT_REVIEW',reason_fa=reason,supporting_spans=[]) for k,cl in enumerate(claims)],
        answer_units=[dict(text=out['response']['answer_text'],kind='FACTUAL' if claims else 'ABSTENTION',claim_indices=list(range(len(claims))),reason_fa=reason)],
        abstention_review='REVIEW_REQUIRED',independent_semantic_entailment='NOT_EVALUATED')
    d=dict(audit=audit,support=support);results={'disjoint_complete_ownership':True}
    def reject(name,fn):
        try:fn()
        except (AssertionError,KeyError,ValueError):results[name]=True;return
        raise AssertionError('Invalid fixture accepted: '+name)
    reject('candidate_outside_range',lambda:apply(baseline(),[d],assignments[1],inputs,outputs))
    reject('duplicate_candidate_in_batch',lambda:apply(baseline(),[d,d],a,inputs,outputs))
    x=copy.deepcopy(d);x['audit']['position']=17
    reject('position_id_mismatch',lambda:apply(baseline(),[x],a,inputs,outputs))
    x=copy.deepcopy(d);x['support']['response_sha256']='0'*64
    reject('active_response_hash_mismatch',lambda:apply(baseline(),[x],a,inputs,outputs))
    x=copy.deepcopy(d);x['support']['claim_results']=[]
    if claims:reject('missing_claim_review',lambda:apply(baseline(),[x],a,inputs,outputs))
    x=copy.deepcopy(d);x['audit']['gold_used_for_review']=True
    reject('gold_used_rejected',lambda:apply(baseline(),[x],a,inputs,outputs))
    with tempfile.TemporaryDirectory(dir=RECOVERY.parents[3],prefix='parallel_isolation_') as name:
        work=Path(name)
        pointer=commit_batch(a,work,inputs,outputs,[d],'batch_0001')
        assert pointer['reviewed']==1 and pointer['pending']==377
        assert len((work/'batches/batch_0001/ledger.jsonl').read_text().splitlines())==1
        results['only_batch_delta_ledger_saved']=True
        current_hash=sha((work/'CURRENT.json').read_bytes())
        assert commit_batch(a,work,inputs,outputs,[d],'batch_0001')==pointer
        assert sha((work/'CURRENT.json').read_bytes())==current_hash
        results['idempotent_no_overwrite']=True
        checkpoint=work/'batches/batch_0001/audit.jsonl';original=checkpoint.read_bytes();checkpoint.write_bytes(original+b'\n')
        reject('tampered_checkpoint_rejected',lambda:load_worker(a,work,inputs,outputs))
        checkpoint.write_bytes(original)
        current=json.loads((work/'CURRENT.json').read_text());current['completed_candidate_ids']=[]
        (work/'CURRENT.pending.json').write_text(json.dumps(current))
        reject('invalid_pending_pointer_rejected_before_publication',lambda:load_worker(a,work,inputs,outputs,pointer=work/'CURRENT.pending.json'))
        assert sha((work/'CURRENT.json').read_bytes())==current_hash
        results['original_pointer_preserved_on_pending_failure']=True
    assert before=={n:sha((RECOVERY/n).read_bytes()) for n in before}
    results['coordinator_15_unchanged']=True
    assert all(not (PARALLEL/f'workers/auditor_{k}/CURRENT.json').exists() for k in [1,2,3])
    results['no_real_worker_progress_created']=True
    return results

if __name__=='__main__':print(json.dumps(run(),indent=2))
