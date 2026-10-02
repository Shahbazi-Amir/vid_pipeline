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
    a=decision(382,'تمام ده شاهد خوانده شد. صفر حاصل تلاش آکادمی را تا زمان متن انتشار بیش از صد جلد کتاب می‌گوید. پاسخ طبق متن را حفظ می‌کند و نه عدد دقیق و نه تعداد جاری2026 است. کتاب‌های ناشران دیگر و بررسی یا ترویج آنها در شواهد دیگر با انتشار مستقل خلط نشده و تعداد300 یادداشت،40 رادیویی یا20 تلویزیونی جای تعداد جلد ننشسته است.',[[(0,'نتیجۀ این تلاش‌ها تا کنون انتشار بیش از صد جلد کتاب بوده است.','بیش از صد جلد همان عدد نامساوی پاسخ است و تا کنون مربوط به زمان متن است.')]])
    b=decision(383,'تمام ده شاهد خوانده شد. صفر رفتار درست نتیجه‌بخش را موجب شکل‌گیری ارزش‌ها معرفی می‌کند و پاسخ قید نتیجه‌بخش و امکان را نگه می‌دارد. سؤال نتیجه کلی دارد اما پاسخ فقط یک پیامد مستند را می‌گوید؛ احساس خوب بخشندگی در اول و اعتماد خوش‌حسابی در ششم پیامدهای دیگری‌اند و ادعای یگانگی نشده است. رفتار بد و مشکلات مالی در هفتم و نهم درباره تغییر ارزش‌اند نه نقیض رابطه پاسخ.',[[(0,'وقتی رفتار درست نتیجه‌بخش بود، آن ارزش‌ها هم شکل می‌گیرد.','شرط نتیجه‌بخشی و شکل‌گیری ارزش‌ها مستقیم است؛ پاسخ می‌تواند از قطعیت فراتر نمی‌رود.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==863
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0033';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[382,383],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0033/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=69,total_reviewed=865,remaining=284,next_position=384)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_382_383_v1',[382,383],'دو KEEP382 و383؛ ادامه384.',cp['created_utc'])
