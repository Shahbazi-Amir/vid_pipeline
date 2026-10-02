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
    a=decision(672,'تمام ده شاهد خوانده شد. سوم نامحدود بودن خواست‌ها و حدگذاری نشدنشان را برای هر انسان می‌گوید. دوم عادت به داشته‌ها و ششم تفاوت خواسته و نیاز مکمل‌اند؛ پاسخ درباره خواسته‌هاست، نه نامحدود بودن نیاز اساسی یا منابع و نه ناممکن بودن مدیریت رفتار مصرف.',[[(3,'یه بعدی که همین\u200cجا بهش بپردازیم، خواست\u200cهاست. یعنی ما خواست\u200cهای نامحدود هم داریم. اون چیزهایی که ماها، هر انسانی در واقع\n\nطالبشه، این\u200cها هیچ وقت قابل در واقع حدگذاری نیست.','نامحدود بودن خواسته و هر انسانی و حدگذاری نشدن مستقیم‌اند.')]])
    b=decision(673,'تمام ده شاهد خوانده شد. صفر مدت استخدام و شاگردی را فردی و شش یا ده سال را مثال می‌داند؛ پاسخ همین قید را حفظ می‌کند. سوم سه تا پنج سال حرفه‌ای شدن، هفتم و هشتم تجربه داوطلبانه یک یا سه ماه، نهم ساعات روزانه و چهارم سهم عمر موضوعات جدا هستند. پاسخ مدت اشتغال همه افراد یا عدد لازم و قطعی را نمی‌گوید.',[[(0,'از نظر تربیتی، شروع از استخدام و شاگردی مفید است. مدت آن برای هر کسی متفاوت است؛ شاید شش سال، شاید ده سال.','مدت متفاوت و شش و ده سال به صورت مثال صریح‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==887
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0045';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[672,673],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0045/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=93,total_reviewed=889,remaining=260,next_position=674)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_672_673_v1',[672,673],'دو KEEP672 و673؛ ادامه674.',cp['created_utc'])
