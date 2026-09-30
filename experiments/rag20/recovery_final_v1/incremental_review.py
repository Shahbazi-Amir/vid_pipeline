"""Offline explicit AGENT_REVIEW persistence. No automatic semantic decisions.

CURRENT commits an immutable generation. Root files are convenient mirrors;
restore mirrors from CURRENT after an interrupted publication. No model APIs.
"""
import argparse
import copy
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from audit_structure import ROOT, rows, sha, canonical, save, validate_schema

STATE = ['candidate_ledger.jsonl', 'audit.jsonl', 'support.jsonl',
         'repairs.jsonl', 'review_queue.jsonl', 'validation.json', 'PROGRESS_FA.md']
SOURCE = 'ebfadb00263a18af5dbd53931f18b434a7c7acb1'

def index(records):
    result = {r['candidate_id']: r for r in records}
    assert len(result) == len(records), 'duplicate candidate'
    return result

def source_rows():
    return rows(ROOT/'inputs.jsonl'), rows(ROOT/'outputs.jsonl')

def preserve(previous, state):
    old=index(previous['audit.jsonl']);new=index(state['audit.jsonl'])
    assert set(old)<=set(new), 'previous audit deleted'
    assert set(index(previous['support.jsonl']))<=set(index(state['support.jsonl'])), 'previous support deleted'
    for r in previous['repairs.jsonl']:
        assert r in state['repairs.jsonl'], 'previous revision deleted or modified'
    for cid,a in old.items():
        if new[cid]!=a:
            assert new[cid].get('revision',0)>a.get('revision',0), 'decision overwritten without new revision'
            assert any(r['candidate_id']==cid and r['previous_response_sha256']==a['response_sha256']
                       for r in state['repairs.jsonl']), 'missing revision lineage'
        else:
            assert index(previous['support.jsonl'])[cid]==index(state['support.jsonl'])[cid]

def load(directory):
    return {n: rows(directory/n) for n in STATE if n.endswith('.jsonl')}

def active(original, repairs):
    result = copy.deepcopy(original)
    revisions = {}
    for r in repairs:
        cid = r['candidate_id']
        assert r['revision'] == revisions.get(cid, 0)+1
        assert r['previous_response_sha256'] == canonical(result[cid]['response'])
        assert r['original_response_sha256'] == original[cid]['response_sha256']
        assert r['original_response'] == original[cid]['response']
        assert r['revised_response_sha256'] == canonical(r['revised_response'])
        result[cid]['response'] = r['revised_response']
        result[cid]['response_sha256'] = r['revised_response_sha256']
        revisions[cid] = r['revision']
    return result, revisions

def validate(state, inputs, outputs):
    ib, ob = index(inputs), index(outputs)
    led, aud, sup = (index(state[n]) for n in STATE[:3])
    assert list(ib) == list(ob) == list(led) and len(ib) == 1149
    assert set(aud) == set(sup) <= set(ib)
    act, revisions = active(ob, state['repairs.jsonl'])
    dimensions = {'evidence_sufficiency','question_answer_fit','factual_claim_support',
                  'scope_modality_negation_quantity','outside_details',
                  'abstention_justified','ambiguity_conflict'}
    for cid, original in ob.items():
        assert canonical(original['response']) == original['response_sha256']
        assert led[cid]['original_response_sha256'] == original['response_sha256']
        rev = revisions.get(cid, 0)
        revision_id = ('revision_%d@'%rev if rev else 'original@')+act[cid]['response_sha256']
        assert led[cid]['active_revision_id'] == revision_id
        if cid not in aud:
            assert led[cid]['semantic_status'] != 'AGENT_REVIEW_COMPLETE'
            assert led[cid]['status'] not in {'KEEP','REPAIRED','VALID_ABSTENTION'}
            continue
        a, s = aud[cid], sup[cid]
        assert a['position'] == led[cid]['position']
        assert a['response_sha256'] == s['response_sha256'] == act[cid]['response_sha256']
        assert a.get('revision',0) == s.get('revision',0) == rev
        assert led[cid]['semantic_status'] == 'AGENT_REVIEW_COMPLETE'
        assert led[cid]['status'] == a['status']
        assert a['method'] == s['method'] == 'AGENT_REVIEW'
        assert a['full_evidence_reviewed'] and not a['context_independence']
        assert not a['gold_used_for_review'] and dimensions <= set(a['dimensions'])
        payload = json.loads(ib[cid]['messages'][1]['content'])
        assert a['evidence_ids_reviewed'] == [e['evidence_id'] for e in payload['evidence']]
        ev = {e['evidence_id']:e['text'] for e in payload['evidence']}
        response = act[cid]['response']; validate_schema(response,payload['response_schema'])
        claims = response['claims']; cr = s['claim_results']
        assert [r['claim_index'] for r in cr] == list(range(len(claims)))
        for cl, result in zip(claims, cr):
            assert canonical(cl) == result['claim_sha256']
            assert cl['claim_text'] == result['claim_text']
            assert cl['evidence_ids'] == result['evidence_ids']
            assert set(cl['evidence_ids']) <= set(ev)
            assert result['reason_fa']
            if result['outcome'] == 'SUPPORTED': assert result['supporting_spans']
            for sp in result['supporting_spans']:
                assert sp['evidence_id'] in cl['evidence_ids']
                text = ev[sp['evidence_id']]
                assert 0 <= sp['start'] < sp['end'] <= len(text)
                assert text[sp['start']:sp['end']] == sp['quote']
            if a['status'] in {'KEEP','REPAIRED'}: assert result['outcome'] == 'SUPPORTED'
        if a.get('schema_version') == 2:
            assert a['answer_factual_coverage_reviewed'] is True
            coverage = s['answer_units']
            assert coverage and ''.join(u['text'] for u in coverage) == response['answer_text']
            for u in coverage:
                assert u['reason_fa'] and set(u['claim_indices']) <= set(range(len(claims)))
                if u['kind'] == 'FACTUAL': assert u['claim_indices']
        if a['status'] == 'VALID_ABSTENTION':
            assert not claims and a['dimensions']['abstention_justified'] == 'JUSTIFIED'
    assert state['review_queue.jsonl'] == [a for a in state['audit.jsonl'] if a['status']=='REVIEW_REQUIRED']
    counts = Counter(a['status'] for a in aud.values())
    assert set(counts) <= {'KEEP','REPAIRED','REVIEW_REQUIRED','VALID_ABSTENTION'}
    next_pos = next((l['position'] for l in state['candidate_ledger.jsonl'] if l['candidate_id'] not in aud), None)
    return dict(semantic_reviewed=len(aud), kept=counts['KEEP'],repaired=counts['REPAIRED'],
                valid_abstention=counts['VALID_ABSTENTION'],review_required_reviewed=counts['REVIEW_REQUIRED'],
                pending_semantic=1149-len(aud),next_semantic_position=next_pos,
                accepted=counts['KEEP']+counts['REPAIRED']+counts['VALID_ABSTENTION'],
                semantics_complete=len(aud)==1149,nb19_nb20_import_ready=False,
                answer_coverage_legacy_pending=sum(a.get('schema_version')!=2 for a in aud.values()))

def verify_current(restore=False):
    current = json.loads((ROOT/'checkpoints/CURRENT.json').read_text())
    directory = ROOT/current.get('snapshot_path','.')
    for name,h in current['files'].items():
        assert sha((directory/name).read_bytes()) == h, name
    for name,h in current.get('source_files',{}).items():
        assert sha((ROOT/name).read_bytes()) == h, 'fixed source changed: '+name
    if restore and directory != ROOT:
        for name in STATE:
            tmp = ROOT/(name+'.restore.tmp'); shutil.copyfile(directory/name,tmp);os.replace(tmp,ROOT/name)
    state = load(directory)
    counts = validate(state,*source_rows())
    assert counts['semantic_reviewed'] == current['semantic_complete']
    assert counts['next_semantic_position'] == current['next_semantic_position']
    return current,state

def publish(state, snapshot_name, positions, notes, start_utc):
    inputs, outputs = source_rows();counts = validate(state,inputs,outputs)
    current,previous = verify_current()
    preserve(previous,state)
    old = json.loads((ROOT/'validation.json').read_text())
    old.update(counts,schema_version='incremental_validation_v2',source_location_validation='NOT_RUN',
               nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN',semantic_method='AGENT_REVIEW',
               revision_hashes_and_claim_spans='PASS',saved_file_reload='PASS',
               semantic_entailment_validation='AGENT_REVIEW_ONLY_NOT_INDEPENDENT',
               review_required_pending_semantic=counts['pending_semantic'])
    stamp = datetime.now(timezone.utc).isoformat()
    target = ROOT/'checkpoints'/snapshot_name
    assert not target.exists(), 'immutable checkpoint already exists'
    temp = target.with_name(target.name+'.staging');temp.mkdir()
    for n in state: save(temp/n,state[n],True)
    save(temp/'validation.json',old)
    progress = f'''# پیشرفت ممیزی محتوایی

بستهٔ میانی؛ آمادهٔ import در NB19/NB20 نیست.

- بررسی‌شده: {counts['semantic_reviewed']}/1149؛ حفظ‌شده: {counts['kept']}؛ اصلاح‌شده: {counts['repaired']}؛ امتناع معتبر: {counts['valid_abstention']}؛ review: {counts['review_required_reviewed']}.
- بررسی‌نشده: {counts['pending_semantic']}؛ اولین position بررسی‌نشده: {counts['next_semantic_position']}.
- آخرین زیرگروه: {positions}؛ زمان واقعی ثبت UTC: {stamp}؛ شروع نوبت UTC: {start_utc}.
- snapshot تولید: {SOURCE}؛ روش AGENT_REVIEW؛ استقلال verifier و تأیید انسانی ادعا نمی‌شود.
- بررسی‌شدن، پذیرفته‌شدن ({counts['accepted']}) و import-ready (false) جدا هستند.
- {notes}
- وابستگی‌ها و روش بازیابی: DEPENDENCIES.json و RECOVERY.md. source/location، adapter و handoff هنوز NOT_RUN هستند.
- {counts['answer_coverage_legacy_pending']} ممیزی قبلی قرارداد تفکیک بندهای پاسخ نسخهٔ ۲ را ندارد؛ حذف یا دوباره تأیید نشده و پیش از تحویل نهایی باید تکمیل شود.
- گام بعد: خواندن کامل position {counts['next_semantic_position']}؛ حفظ همهٔ تصمیم‌ها و اصلاحات موجود.
'''
    (temp/'PROGRESS_FA.md').write_text(progress)
    assert validate(load(temp),inputs,outputs) == counts
    files={n:sha((temp/n).read_bytes()) for n in STATE}
    manifest=dict(schema_version=2,run_id='recovery_final_v1',source_commit=SOURCE,
                  snapshot_path=str(target.relative_to(ROOT)),files=files,
                  completed_candidate_ids=[a['candidate_id'] for a in state['audit.jsonl']],
                  semantic_complete=counts['semantic_reviewed'],last_checkpoint_success=snapshot_name,
                  positions_completed=positions,created_utc=stamp,session_start_utc=start_utc,
                  timing_note='session_start_utc is first measured anchor; actual turn start was not instrumented',
                  previous_checkpoint=current.get('snapshot_path','legacy_001_005'),
                  source_files={n:sha((ROOT/n).read_bytes()) for n in ['inputs.jsonl','outputs.jsonl']},
                  **{k:v for k,v in counts.items() if k!='semantic_reviewed'})
    save(temp/'checkpoint.json',manifest)
    os.replace(temp,target)
    # Commit pointer atomically before publishing recoverable convenience mirrors.
    save(ROOT/'checkpoints/CURRENT.json',manifest)
    verify_current(restore=True)
    print(json.dumps(counts,ensure_ascii=False))

def append_decisions(state, decisions):
    inputs,outputs=source_rows();ob=index(outputs);ib=index(inputs)
    for d in decisions:
        cid=d['audit']['candidate_id'];a=d['audit'];s=d['support']
        existing=index(state['audit.jsonl']).get(cid)
        if existing:
            if existing==a:
                assert index(state['support.jsonl'])[cid]==s, 'conflicting rerun'
                if d.get('repair'): assert d['repair'] in state['repairs.jsonl']
                continue
            assert d.get('repair'), 'overwrite needs an explicit revision'
            assert a['revision']==existing.get('revision',0)+1
            assert d['repair']['previous_response_sha256']==existing['response_sha256']
            state['audit.jsonl']=[r for r in state['audit.jsonl'] if r['candidate_id']!=cid]
            state['support.jsonl']=[r for r in state['support.jsonl'] if r['candidate_id']!=cid]
        if d.get('repair'):state['repairs.jsonl'].append(d['repair'])
        state['audit.jsonl'].append(a);state['support.jsonl'].append(s)
        ledger=index(state['candidate_ledger.jsonl'])[cid]
        rev=a['revision'];ledger.update(status=a['status'],semantic_status='AGENT_REVIEW_COMPLETE',
            semantic_method='AGENT_REVIEW',handoff_ready=False,
            active_revision_id=('revision_%d@'%rev if rev else 'original@')+a['response_sha256'],
            active_response_sha256=a['response_sha256'],revision=rev,
            review_reason=a['reason_fa'] if a['status']=='REVIEW_REQUIRED' else None)
    for n in ['audit.jsonl','support.jsonl']:state[n].sort(key=lambda a:index(state['candidate_ledger.jsonl'])[a['candidate_id']]['position'])
    state['review_queue.jsonl']=[a for a in state['audit.jsonl'] if a['status']=='REVIEW_REQUIRED']
    validate(state,inputs,outputs)
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--restore',action='store_true')
    args=parser.parse_args();c,s=verify_current(args.restore)
    print(json.dumps(validate(s,*source_rows()),ensure_ascii=False))
