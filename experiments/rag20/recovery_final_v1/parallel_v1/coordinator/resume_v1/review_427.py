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
    return [decision(427,'تمام ده شاهد اصلی سالم دوباره خوانده شد. ممیزی قدیمی427 به دلیل خرابی فایل و هش کنار گذاشته شده بود و این تصمیم مستقل از آن ردیف خراب بازساخته می‌شود. صفر تورم را افزایش سطح قیمت کالاها و خدمات تعریف می‌کند؛ پنجم افزایش عمومی و نهم ماندگاری و همه بازارها را توضیح می‌دهند. پاسخ سطح قیمت است نه گران‌شدن یک کالای خاص؛ سازوکار چاپ پول یا سرمایه‌گذاری انحصاری به پاسخ کوتاه افزوده نشده و تعریف با کاهش قدرت خرید سایر شواهد ناسازگار نیست.',[[(0,'«تورم»، افزایش سطح قیمت کالاها و خدمات است.','تعریف پاسخ عیناً در شاهد سالم آمده و claim کامل پشتیبانی شده است.')]])]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==875
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0039';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[427],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0039/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=80,total_reviewed=876,remaining=273,next_position=661)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_427_v1',[427],'KEEP427 با شواهد سالم بازسازی شد؛ ادامه661.',cp['created_utc'])
