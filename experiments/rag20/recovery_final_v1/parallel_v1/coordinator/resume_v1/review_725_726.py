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
    a=decision(725,'تمام ده شاهد خوانده شد. صفر صریحاً می‌گوید نرخ روزشمار مطرح ولی توضیح داده نشده و مثال۲۰ درصد سالانه را به فکر و تمرین واگذار می‌کند. سوم و چهارم مثال مرکب سالانه و دوم مانده ماهانه‌اند و فرمول روزشمار ارائه نمی‌کنند. پاسخ درباره همین بخش محاسبات است نه فقدان هر توضیح نرخ بهره در کل شواهد.',[[(0,'یه چیزی که ما در موردش صحبت کردیم و توضیحش ندادیم همون نرخ بهره‌ایه که روزشمار محاسبه می‌شه.','نقص توضیح محاسبه روزشمار مستقیم است.'),(0,'نرخ بهره سالانه ۲۰ درصد','مثال نرخ سالانه بیست درصد در همین قطعه است.')]])
    b=decision(726,'تمام ده شاهد خوانده شد. صفر عدم‌اطمینان را از شرایط همیشگی تصمیم مالی معرفی و پذیرش آن را صریح می‌گوید. اول دوم و سوم پذیرش شرایط خارج کنترل و اقدام در محدوده کنترل را تکمیل می‌کنند. پاسخ پذیرش عدم‌اطمینان است نه تسلیم و کنار گذاشتن برنامه‌ریزی.',[[(0,'باید عدم‌اطمینان رو به‌عنوان یکی از شرایط بپذیریم.','پذیرش عدم‌اطمینان مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==940
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0071';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[725,726],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0071/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=146,total_reviewed=942,remaining=207,next_position=727)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_725_726_v1',[725,726],'دو KEEP725 و726؛ ادامه727.',cp['created_utc'])
