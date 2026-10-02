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
    return [decision(368,'تمام ده شاهد خوانده شد. صفر منابع پراکنده تاریخی را با ارائه جامع و استاندارد جهانی مقایسه می‌کند و کتاب سنگ‌بناهای سواد مالی با طبقه‌بندی پیش‌دبستانی تا انتهای دبیرستان را مثال می‌زند. پاسخ با عبارت مثال می‌زند دامنه را محدود می‌کند و کتاب را یگانه منشأ همه آموزه‌ها معرفی نمی‌کند. شاهد دوم استاندارد دیگری با تعداد متفاوت مفاهیم است؛ پاسخ عددی نگفته و دو چارچوب را یکی نکرده است. منابع دینی در هفتم و هشتم آموزه‌های دقیق دیگری دارند اما انحصار در پاسخ وجود ندارد.',[[(0,'یعنی همون یه کتابی هست تحت عنوان «سنگ‌بناهای سواد مالی» تو ایران هم منتشر شده؛ اون ۱۲۷ مفهوم تقسیم شده به ۱۴ سال، از پیش‌دبستانی تا انتهای دبیرستان. یعنی این‌قدر مشخص و دقیق طبقه‌بندی شده.','نام کتاب و دامنه آموزشی و طبقه‌بندی دقیق همه در این عبارت مستقیم آمده‌اند.')]])]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==849
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0024';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[368],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0024/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=54,total_reviewed=850,remaining=299,next_position=369)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_368_v1',[368],'KEEP368؛ ادامه369.',cp['created_utc'])
