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
    a=decision(693,'تمام ده شاهد خوانده شد. صفر دقت و صراحت و وکالت‌نامه مختص کار با حدود و شرایط را صریح می‌گوید. پاسخ در بافت واگذاری به وکیل است؛ درباره واگذاری دارایی پس از مرگ یا مشارکت خانوادگی حکم جدیدی نمی‌سازد. پنجم و هشتم اهمیت مکتوب‌بودن و نهم حفظ اطلاعات مکمل‌اند؛ الزام حقوقی تازه یا شرایط قانونی امروز اضافه نشده است.',[[(0,'واگذاری امور مالی نیازمند دقت و صراحت است. اگر لازم است کاری را وکیل انجام دهد، متن وکالت‌نامه مختص همان کار، با تعیین حدود و شرایط تنظیم شود','دقت و صراحت و اختصاص کار و حدود روشن مستقیم‌اند.')]])
    b=decision(694,'تمام ده شاهد خوانده شد. صفر قانون مالیات خانه خالی و در جریان بودن تصحیح در زمان روایت را می‌گوید. پاسخ به متن نسبت می‌دهد؛ دیگر نرخ‌های ارث و اجاره و حقوق موضوع دیگری هستند. جمله عدم مشخص بودن اجرای کنونی محدودیت زمانی مجموعه شواهد است؛ زمان سند و گزارش اجرای امروز در هیچ یک نیست. عدم اجرا در زمان روایت را به امروز تعمیم نداده و شماره ماده یا نرخ خانه خالی حدس نزده است.',[[(0,'مالیات بر خانه‌های خالیه که جدیدی شده، قانونش وجود داره و داره یه تصحیح‌هایی می‌شه.','وجود قانون و اصلاحات در روایت مستقیم است؛ اجرای امروز از این جمله معلوم نیست.')]],units=[dict(text='متن از وجود قانون مالیات بر خانه‌های خالی و اصلاحاتی در آن خبر می‌دهد؛',kind='FACTUAL',claim_indices=[0],reason_fa='نقل محتوای متن'),dict(text=' وضعیت کنونی اجرای آن در این شواهد مشخص نیست.',kind='EVIDENCE_LIMITATION',claim_indices=[],reason_fa='گزارش زمان‌دار اجرای کنونی در ده شاهد وجود ندارد')])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==908
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0055';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[693,694],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0055/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=114,total_reviewed=910,remaining=239,next_position=695)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_693_694_v1',[693,694],'دو KEEP693 و694؛ ادامه695.',cp['created_utc'])
