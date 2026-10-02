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
    a=decision(680,'تمام ده شاهد خوانده شد. صفر ترتیب پنج پله را کامل می‌گوید و اول و دوم و پنجم تأیید می‌کنند. امنیت و تاب‌آوری دو نام یک پله‌اند نه دو مرحله جدا؛ پاسخ همین ترکیب را حفظ کرده است. سرفصل‌های شش‌گانه سواد مالی در سوم و چهارم و هفتم و هشتم با پله‌های توانمندی خلط نشده‌اند.',[[(0,'از ناتوانی مالی به تقلای مالی، از تقلای مالی به تعادل مالی، از تعادل مالی به امنیت و تاب‌آوری مالی، و از امنیت مالی به آزادی مالی.','ترتیب همه مراحل دقیق و مستقیم است.')]])
    b=decision(681,'تمام ده شاهد خوانده شد. صفر مسئله بالاتر بودن هزینه از درآمد و دو راه کاهش هزینه یا افزایش درآمد را صریح می‌گوید. پنجم همین معادله را توضیح می‌دهد و قرض را راه حل پایدار آن نمی‌داند؛ سوم و ششم مدیریت هزینه و نقدشوندگی کمک اجرایی هستند. پاسخ عدم تعادل دخل و خرج را هدف می‌گیرد و حل قطعی هر بحران یا سرمایه‌گذاری فوری برای پول ناموجود نمی‌گوید.',[[(0,'مهم‌ترین و تنها مسأله مالی یک فرد و خانواده عدم تعادل دخل و خرج و به بیان دقیق‌تر، بالاتر بودن هزینه‌ها در برابر درآمدهاست. به منظور حل مسألۀ مالی، باید مستقیم دست‌به‌کار شد. دو راه بیشتر وجود ندارد: کاهش هزینه‌ها یا افزایش درآمد.','مسئله و دو راه مستقیم‌اند؛ عبارت تنها مسئله به پاسخ اضافه نشده است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==895
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0049';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[680,681],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0049/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=101,total_reviewed=897,remaining=252,next_position=682)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_680_681_v1',[680,681],'دو KEEP680 و681؛ ادامه682.',cp['created_utc'])
