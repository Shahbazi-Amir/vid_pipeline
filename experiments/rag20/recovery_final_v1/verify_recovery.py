"""Reload saved recovery artifacts and exercise meaningful negative cases."""
import copy
import json
from audit_structure import ROOT, BASE, rows, sha, canonical, validate_pair, save

def reject(fn):
    try:fn()
    except (AssertionError,KeyError,ValueError):return True
    raise AssertionError('Corrupted fixture was accepted')

def validate_ids(records):
    ids=[r['candidate_id'] for r in records]
    assert len(ids)==len(set(ids))

def validate_span(text,span):
    assert 0<=span['start']<span['end']<=len(text)
    assert text[span['start']:span['end']]==span['quote']

def main():
    ins=rows(ROOT/'inputs.jsonl');outs=rows(ROOT/'outputs.jsonl');ledger=rows(ROOT/'candidate_ledger.jsonl')
    validate_ids(ins);validate_ids(outs);validate_ids(ledger)
    assert [r['candidate_id'] for r in ins]==[r['candidate_id'] for r in outs]==[r['candidate_id'] for r in ledger]
    assert len(ins)==1149
    audits=rows(ROOT/'audit.jsonl');supports=rows(ROOT/'support.jsonl')
    by_id={r['candidate_id']:r for r in ins};out_by_id={r['candidate_id']:r for r in outs}
    for audit in audits:
        assert audit['response_sha256']==out_by_id[audit['candidate_id']]['response_sha256']
        assert audit['full_evidence_reviewed'] is True
        assert audit['context_independence'] is False
    for sup in supports:
        cid=sup['candidate_id']; ev={e['evidence_id']:e['text'] for e in json.loads(by_id[cid]['messages'][1]['content'])['evidence']}
        assert sup['response_sha256']==out_by_id[cid]['response_sha256']
        claims=out_by_id[cid]['response']['claims']
        assert len(claims)==len(sup['claim_results'])
        for cl in sup['claim_results']:
            assert canonical(claims[cl['claim_index']])==cl['claim_sha256']
            for sp in cl['supporting_spans']:
                assert sp['evidence_id'] in cl['evidence_ids']
                validate_span(ev[sp['evidence_id']],sp)
    inp=ins[0];out=outs[0];payload=json.loads(inp['messages'][1]['content'])
    registry={e['evidence_id']:{'content':e['text'],'content_sha256':sha(e['text'].encode())} for e in payload['evidence']}
    packet={'candidate_id':inp['candidate_id'],'split':'test','evidence_refs':[{'evidence_id':e['evidence_id']} for e in payload['evidence']]}
    args=(packet,registry,payload['question'])
    wrong=copy.deepcopy(out);wrong['response']['claims'][0]['evidence_ids']=['INVALID_EVIDENCE'];wrong['response_sha256']=canonical(wrong['response'])
    tests={'invalid_claim_evidence_id':reject(lambda:validate_pair(inp,wrong,*args)),'duplicate_candidate':reject(lambda:validate_ids([inp,inp]))}
    wrong=copy.deepcopy(out);wrong['response_sha256']='0'*64
    tests['response_hash_mismatch']=reject(lambda:validate_pair(inp,wrong,*args))
    tests['out_of_range_support_span']=reject(lambda:validate_span('abc',{'start':0,'end':4,'quote':'abc'}))
    tests['span_text_mismatch']=reject(lambda:validate_span('abc',{'start':0,'end':2,'quote':'zz'}))
    wrong=copy.deepcopy(inp);p=json.loads(wrong['messages'][1]['content']);p['evidence'][0]['text']+='tamper';wrong['messages'][1]['content']=json.dumps(p);wrong['messages_sha256']=canonical(wrong['messages']);wrongout=copy.deepcopy(out);wrongout['messages_sha256']=wrong['messages_sha256']
    tests['full_evidence_text_tampered']=reject(lambda:validate_pair(wrong,wrongout,*args))
    v=json.loads((ROOT/'validation.json').read_text())
    v.update(semantic_reviewed=len(audits),kept=sum(r['status']=='KEEP' for r in audits),review_required_reviewed=sum(r['status']=='REVIEW_REQUIRED' for r in audits),review_required_pending_semantic=1149-len(audits),negative_tests=tests,independent_file_reload='PASS',semantic_method='AGENT_REVIEW_SHARED_CONTEXT',semantics_complete=False)
    save(ROOT/'validation.json',v)
    save(ROOT/'checkpoints/CURRENT.json',{'run_id':'recovery_final_v1','source_commit':v['source_commit'],'structural_complete':1149,'semantic_complete':len(audits),'next_semantic_position':len(audits)+1,'kept':v['kept'],'review_required_reviewed':v['review_required_reviewed'],'pending_semantic':1149-len(audits),'original_outputs_preserved':True,'files':{name:sha((ROOT/name).read_bytes()) for name in ['candidate_ledger.jsonl','audit.jsonl','support.jsonl','outputs.jsonl','validation.json']},'next_step':'Continue semantic review, then selective repairs, source/location validation, NB19 adapter, and final freeze. No API calls; do not modify RAG_finance.'})
    print(json.dumps(v,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
