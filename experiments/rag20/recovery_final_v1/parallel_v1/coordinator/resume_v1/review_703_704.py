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
    a=decision(703,'تمام ده شاهد خوانده شد. صفر ذیل نوسازی بافت فرسوده سه منبع و مجموع پانصد و پنجاه میلیون را مستقیم می‌گوید. پاسخ طبق متن مقید و درباره منابع و مبلغ همین وام است، نه شرایط احراز یا نرخ امروز؛ مبلغ روستایی یا نهضت ملی با آن خلط نشده و دسترسی همگانی کاربر را تضمین نمی‌کند.',[[(0,'از سه منبع دولت، منابع بدون سپردۀ بانک و اوراق ممتاز مجموعاً 550میلیون تومان تسهیلات شصت‌ماهه دریافت کنید.','سه منبع و مجموع مبلغ مستقیم‌اند.')]])
    b=decision(704,'تمام ده شاهد خوانده شد. هفتم پنج مرحله را به ترتیب می‌آورد و صفر و اول تعداد پنج و اول همه نام‌ها و پنجم شماره چهارم و پنجم را تأیید می‌کنند. در هفتم شمار پنج از پنج نام مستقیم معلوم است؛ امنیت و تاب‌آوری دو نام پله واحدند و تعادل مالی همان تعادل دخل‌وخرج است. تعداد سرفصل و مفهوم در ششم و هشتم با تعداد پله خلط نشده است.',[[(7,'از ناتوانی مالی بریم به تقلای مالی، بریم به تعادل مالی، امنیت مالی و در نهایت آزادی مالی.','پنج نام و ترتیب مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==918
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0060';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[703,704],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0060/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=124,total_reviewed=920,remaining=229,next_position=705)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_703_704_v1',[703,704],'دو KEEP703 و704؛ ادامه705.',cp['created_utc'])
