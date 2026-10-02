"""Explicit full-evidence decisions 328–329."""
import sys,json,copy
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'parallel_v1/shared'))
from decisions_006_010 import decision
from audit_structure import rows,save,sha
import incremental_review as frozen
import range_io

def decisions():
    return [decision(366,'تمام ده شاهد خوانده شد. صفر به صراحت سبک تربیتی یکسان والدین و مربی در امور مالی را می‌گوید؛ پاسخ همان گزاره است. یکسانی سبک مالی همه اطرافیان درخواست نشده و متن چنین انتظاری را رد می‌کند. شواهد دیگر الگو بودن والدین، ابزار تدریس، آموزش پس‌انداز، شرایط بهزیستی و کسب درآمد نوجوان را توضیح می‌دهند و این گزاره را نقض نمی‌کنند.',[[(0,'مهم آن است که والدین و مربی باید سبک تربیتی یکسانی در امور مالی داشته باشند.','پاسخ و claim واحد دقیقاً سبک تربیتی یکسان والدین و مربی را نقل می‌کنند، نه یکسانی سبک مالی همه دوستان و خانواده.')]])]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==847
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0022';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[366],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0022/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=52,total_reviewed=848,remaining=301,next_position=367)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_366_v1',[366],'KEEP366؛ ادامه367.',cp['created_utc'])
