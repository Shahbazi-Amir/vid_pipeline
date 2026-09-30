"""Negative regressions for recovery, revisions and idempotent writes."""
import copy
import json
from audit_structure import ROOT,sha
from incremental_review import verify_current,append_decisions,validate,source_rows,preserve
from decisions_006_010 import decisions

def run():
    c,s=verify_current();inputs,outputs=source_rows();result={}
    def rejected(name,fn):
        try:fn()
        except (AssertionError,KeyError,ValueError):result[name]=True;return
        raise AssertionError('Corrupted case accepted: '+name)
    replay=append_decisions(copy.deepcopy(s),decisions())
    assert replay==s;result['idempotent_replay_without_duplicates']=True
    x=copy.deepcopy(s);x['audit.jsonl'].append(copy.deepcopy(x['audit.jsonl'][0]))
    rejected('duplicate_audit',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);x['support.jsonl'][0]['response_sha256']='0'*64
    rejected('active_hash_mismatch',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);x['support.jsonl'][0]['claim_results']=[]
    rejected('missing_claim_review',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);x['support.jsonl'][0]['claim_results'][0]['supporting_spans'][0]['end']=10**8
    rejected('invalid_quote_span',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);x['audit.jsonl']=x['audit.jsonl'][1:]
    rejected('accidental_previous_deletion',lambda:preserve(s,x))
    x=copy.deepcopy(s);x['repairs.jsonl'][0]['previous_response_sha256']='0'*64
    rejected('broken_revision_lineage',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);x['repairs.jsonl'].append(copy.deepcopy(x['repairs.jsonl'][0]))
    rejected('duplicate_revision',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);x['candidate_ledger.jsonl'][15]['status']='KEEP'
    rejected('unreviewed_keep',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);x['support.jsonl'][5]['answer_units'][0]['claim_indices']=[]
    rejected('unmapped_factual_answer',lambda:validate(x,inputs,outputs))
    x=copy.deepcopy(s);cid=x['audit.jsonl'][6]['candidate_id']
    x['audit.jsonl']=[a for a in x['audit.jsonl'] if a['candidate_id']!=cid]
    x['support.jsonl']=[a for a in x['support.jsonl'] if a['candidate_id']!=cid]
    l=x['candidate_ledger.jsonl'][6];l['status']='REVIEW_REQUIRED';l['semantic_status']='NOT_EVALUATED'
    assert validate(x,inputs,outputs)['next_semantic_position']==7
    result['first_actual_gap_not_review_count_plus_one']=True
    before=sha((ROOT/'checkpoints/CURRENT.json').read_bytes());verify_current()
    assert before==sha((ROOT/'checkpoints/CURRENT.json').read_bytes())
    result['read_only_verifier_preserves_current']=True
    return result

if __name__=='__main__':print(json.dumps(run(),indent=2))
