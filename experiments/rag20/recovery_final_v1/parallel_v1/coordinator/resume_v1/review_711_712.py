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
    a=decision(711,'تمام ده شاهد خوانده شد. صفر تعریف ماهیت مالیات را عیناً دارد. سایر شواهد درباره نقش تنظیمگری، خدمات عمومی، پایه‌ها و قواعد تاریخی نرخ مالیات هستند. پاسخ فقط تعریف است و از نرخ‌ها یا مقررات قدیمی ادعای امروز استخراج نکرده است.',[[(0,'مالیات انتقال اجباری منابع جامعه به مقام دولت یا محلیه، بر اساس معیارهای از پیش تعیین‌شده.','تعریف ماهیت عیناً بیان شده است.')]])
    b=decision(712,'تمام ده شاهد خوانده شد. صفر و اول و سوم و پنجم تعریف دانش مهارت گرایش رفتار و اداره امور مالی را تکرار می‌کنند. ششم و هفتم مدیریت دخل و خرج و اجرا و هشتم و نهم آموزش کودکان را توضیح می‌دهند. پاسخ مطابق متن و در حد هدف پایه اداره امور مالی است و تضمین ثروتمندی نیست.',[[(0,'سواد مالی مجموعه‌ای از دانش‌ها، مهارت‌ها، گرایش‌ها و رفتارهای مالی است که از یک سو به افراد کمک می‌کند سررشتۀ امور مالی‌شان را در دست بگیرند و از سوی دیگر، رشد و شکوفایی اقتصاد جامعه را به دنبال دارد.','چهار مؤلفه و اداره امور مالی مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==926
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0064';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[711,712],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0064/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=132,total_reviewed=928,remaining=221,next_position=713)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_711_712_v1',[711,712],'دو KEEP711 و712؛ ادامه713.',cp['created_utc'])
