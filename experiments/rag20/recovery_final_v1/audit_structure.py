"""Offline, resumable structural audit. Does not infer semantic support."""
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

def validate_schema(value, schema):
    typ = schema.get('type')
    types = {'object':dict,'array':list,'string':str,'boolean':bool,'integer':int,'number':(int,float),'null':type(None)}
    if typ:
        allowed = typ if isinstance(typ,list) else [typ]
        assert any(isinstance(value,types[t]) for t in allowed)
    if 'enum' in schema: assert value in schema['enum']
    if isinstance(value,dict):
        assert set(schema.get('required',[])).issubset(value)
        if schema.get('additionalProperties') is False: assert set(value).issubset(schema.get('properties',{}))
        for key,sub in schema.get('properties',{}).items():
            if key in value: validate_schema(value[key],sub)
    if isinstance(value,list):
        assert len(value)>=schema.get('minItems',0)
        if 'maxItems' in schema: assert len(value)<=schema['maxItems']
        if schema.get('uniqueItems'): assert len({canonical(v) for v in value})==len(value)
        if 'items' in schema:
            for item in value: validate_schema(item,schema['items'])
    if isinstance(value,str): assert len(value)>=schema.get('minLength',0)

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def save(path, value, jsonl=False):
    content = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in value) if jsonl else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(content)
    loaded = rows(tmp) if jsonl else json.loads(tmp.read_text())
    assert loaded == value
    tmp.replace(path)
    return sha(path.read_bytes())

def validate_pair(inp, out, packet, registry, question):
    assert inp['candidate_id'] == out['candidate_id'] == packet['candidate_id']
    assert inp['split'] == packet['split'] == 'test'
    assert canonical(inp['messages']) == inp['messages_sha256'] == out['messages_sha256']
    assert canonical(out['response']) == out['response_sha256']
    assert len(inp['messages']) == 2
    assert [m['role'] for m in inp['messages']] == ['system', 'user']
    payload = json.loads(inp['messages'][1]['content'])
    assert set(payload) == {'question', 'evidence', 'response_schema'}
    assert payload['question'] == question
    refs = [r['evidence_id'] for r in packet['evidence_refs']]
    ids = [r['evidence_id'] for r in payload['evidence']]
    assert ids == refs and len(set(ids)) == len(ids)
    for evidence in payload['evidence']:
        record = registry[evidence['evidence_id']]
        assert evidence['text'] == record['content']
        assert sha(record['content'].encode()) == record['content_sha256']
    validate_schema(out['response'], payload['response_schema'])
    for claim in out['response']['claims']:
        assert claim['claim_text'].strip()
        assert claim['evidence_ids'] and len(set(claim['evidence_ids'])) == len(claim['evidence_ids'])
        assert set(claim['evidence_ids']).issubset(ids)
    return payload

def main():
    snapshot = json.loads((ROOT / 'SOURCE_SNAPSHOT.json').read_text())
    previous_ledger = {r['candidate_id']:r for r in rows(ROOT/'candidate_ledger.jsonl')} if (ROOT/'candidate_ledger.jsonl').exists() else {}
    blobs = {r['path']:r for r in snapshot['source_tree']}
    sources = []
    for path in sorted(BASE.rglob('*')):
        if not path.is_file() or ROOT in path.parents: continue
        rel = str(path.relative_to(BASE.parent.parent))
        if rel not in blobs: continue
        data = path.read_bytes()
        git_sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        assert git_sha == blobs[rel]['git_blob_sha'], rel
        sources.append({'path':rel, 'git_blob_sha':git_sha, 'sha256':sha(data), 'bytes':len(data)})
    sm = json.loads((BASE / 'evidence_shards/manifest.json').read_text())
    registry = {}
    digest = hashlib.sha256()
    for part in sm['parts']:
        path = BASE / 'evidence_shards' / part['path']; data = path.read_bytes()
        assert sha(data) == part['sha256'] and len(data) == part['bytes']
        digest.update(data)
        for row in rows(path):
            assert row['evidence_id'] not in registry
            assert sm['evidence_id_to_part'][row['evidence_id']] == part['path']
            registry[row['evidence_id']] = row
    assert digest.hexdigest() == sm['source_sha256'] and len(registry) == sm['record_count']
    packets = {r['candidate_id']:r for r in rows(ROOT/'source_cache/context_packets_v1.jsonl') if r['split']=='test'}
    for source in snapshot['rag_selected_sources']:
        path=ROOT/'source_cache'/source['path'].split('/')[-1]
        if not path.exists(): continue
        data=path.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==source['git_blob_sha'], source['path']
    questions = {r['candidate_id']:r['question'] for r in rows(ROOT/'source_cache/questions_only.jsonl')}
    catalog = json.loads((BASE/'batches/index.json').read_text())
    ledger, checks, inputs, outputs, citations, exposure = [], [], [], [], [], []
    evidence_counts = Counter(); all_ids = []; total_refs = 0
    citation_fields = ['evidence_id','chunk_id','source_id','source_type','content_origin','member_document_ids','member_documents','member_locators','locator_start','locator_end','attribution_context','authority_signal_metadata','authority_warning_flags','semantic_conflict_status','prompt_injection_pattern_flags']
    for batch in catalog['batches']:
        batch_dir = ROOT/'checkpoints'/batch['directory']
        previous_checks = None
        if (batch_dir/'checkpoint.json').exists():
            old_cp=json.loads((batch_dir/'checkpoint.json').read_text())
            if old_cp['source_commit']==snapshot['source_commit']:
                assert sha((batch_dir/'structural_audit.jsonl').read_bytes())==old_cp['audit_sha256']
                previous_checks=rows(batch_dir/'structural_audit.jsonl')
        ins = rows(BASE/'batches'/batch['inputs']); outs = rows(BASE/'batches'/batch['outputs'])
        manifest = json.loads((BASE/'batches'/batch['manifest']).read_text())
        assert len(ins) == len(outs) == batch['candidate_count'] == manifest['candidate_count']
        ids = [r['candidate_id'] for r in ins]
        assert ids == [r['candidate_id'] for r in outs] == manifest['candidate_ids']
        assert len(set(ids)) == len(ids) and not(set(all_ids)&set(ids))
        for name, path in [('inputs.jsonl',batch['inputs']), ('outputs.jsonl',batch['outputs'])]:
            assert sha((BASE/'batches'/path).read_bytes()) == manifest['files_sha256'][name]
        local_checks = []
        for inp,out in zip(ins,outs):
            cid = inp['candidate_id']
            if previous_checks is None:
                payload = validate_pair(inp,out,packets[cid],registry,questions[cid])
            else:
                assert previous_checks[len(local_checks)]['candidate_id']==cid
                payload=json.loads(inp['messages'][1]['content'])
            evidence_counts[len(payload['evidence'])] += 1; total_refs += len(payload['evidence'])
            position = len(all_ids)+1; all_ids.append(cid)
            row = {'candidate_id':cid,'position':position,'split':'test','status':'REVIEW_REQUIRED','review_reason':'SEMANTIC_AUDIT_NOT_YET_PERFORMED','structural_status':'PASS','semantic_status':'NOT_EVALUATED','active_revision_id':'original@'+out['response_sha256'],'original_response_sha256':out['response_sha256'],'source_commit':snapshot['source_commit'],'input_path':'experiments/rag20/batches/'+batch['inputs'],'output_path':'experiments/rag20/batches/'+batch['outputs'],'handoff_ready':False}
            if cid in previous_ledger and previous_ledger[cid]['source_commit']==snapshot['source_commit'] and previous_ledger[cid]['original_response_sha256']==out['response_sha256']:
                row=previous_ledger[cid]
            ledger.append(row)
            check = {'candidate_id':cid,'position':position,'status':'PASS','checks':['identity','test_split','canonical_messages_hash','canonical_response_hash','question_exact','evidence_id_order','full_evidence_text','registry_content_hash','response_schema','claim_evidence_membership'],'semantic_support':'NOT_EVALUATED'}
            checks.append(check); local_checks.append(check); inputs.append(inp);outputs.append(out)
            exposure.append({'candidate_id':cid,'split':'test','generation_gold_exposure':'UNKNOWN','prior_gold_evaluation':'REPORTED_IN_USER_BRIEF_NOT_INDEPENDENTLY_VERIFIED' if position<=170 else 'UNKNOWN','current_recovery_gold_labels_read':False,'question_source':'isolated_question_only_export','role':'recovery_audit'})
            for eid in dict.fromkeys(e for claim in out['response']['claims'] for e in claim['evidence_ids']):
                er=registry[eid]
                citations.append({'candidate_id':cid,'response_sha256':out['response_sha256'],'content_sha256':er['content_sha256'],'citation':{'citation_id':'recovery_citation_'+canonical([cid,eid])[:24],**{k:er[k] for k in citation_fields}},'attachment_status':'REGISTRY_METADATA_COPIED','location_status':'NOT_VALIDATED_AGAINST_SOURCE_DOCUMENT'})
        h = save(batch_dir/'structural_audit.jsonl',local_checks,True)
        save(batch_dir/'checkpoint.json',{'run_id':'recovery_final_v1','phase':'B_STRUCTURAL','source_commit':snapshot['source_commit'],'batch':batch['directory'],'records_completed':len(ins),'cumulative_structural_count':len(all_ids),'audit_sha256':h,'semantic_count':0,'next_step':'Full semantic audit of question, all evidence, answer and claims. Do not repeat structural checks unless source changes.'})
        print(json.dumps({'batch':batch['directory'],'count':len(ins),'cumulative':len(all_ids),'checkpoint':'SAVED_AND_RELOADED','structural_action':'RESUMED_EXISTING' if previous_checks is not None else 'CHECKED'}))
    assert set(all_ids)==set(packets) and len(all_ids)==len(packets)==1149
    save(ROOT/'candidate_ledger.jsonl',ledger,True)
    save(ROOT/'structural_audit.jsonl',checks,True)
    save(ROOT/'inputs.jsonl',inputs,True); save(ROOT/'outputs.jsonl',outputs,True)
    save(ROOT/'citation_attachments.jsonl',citations,True); save(ROOT/'exposure_ledger.jsonl',exposure,True)
    save(ROOT/'SOURCE_FILE_HASHES.json',sources)
    summary={'schema_version':'recovery_structural_validation_v1','source_commit':snapshot['source_commit'],'candidate_count':len(all_ids),'batch_count':len(catalog['batches']),'unique_candidate_count':len(set(all_ids)),'expected_coverage':'PASS','input_output_hashes':'PASS','evidence_registry_reassembly':'PASS','full_evidence_references_checked':total_refs,'evidence_count_distribution':{str(k):v for k,v in evidence_counts.items()},'structurally_valid':1149,'semantic_reviewed':0,'kept':0,'repaired':0,'valid_abstention':0,'review_required_pending_semantic':1149,'independent_semantic_entailment':'NOT_EVALUATED','gold_evaluation':'NOT_RUN','source_location_validation':'NOT_RUN','nb19_nb20_import_ready':False,'paid_provider_api_calls':0,'saved_file_reload':'PASS'}
    save(ROOT/'validation.json',summary)
    if not (ROOT/'checkpoints/phase_B_complete.json').exists():
        save(ROOT/'checkpoints/phase_B_complete.json',{'run_id':'recovery_final_v1','phase':'B_STRUCTURAL_COMPLETE','source_commit':snapshot['source_commit'],'completed':1149,'semantic_completed':0,'output_sha256':sha((ROOT/'outputs.jsonl').read_bytes()),'ledger_sha256':sha((ROOT/'candidate_ledger.jsonl').read_bytes()),'next_step':'Phase C full-evidence semantic review from position 1; preserve historical outputs.'})
    if (ROOT/'audit.jsonl').exists():
        from verify_recovery import main as verify
        verify()

if __name__=='__main__': main()
