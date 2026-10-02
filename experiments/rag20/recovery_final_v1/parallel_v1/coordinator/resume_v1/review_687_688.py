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
    a=decision(687,'تمام ده شاهد خوانده شد. صفر سرفصل پنجم را مدیریت ریسک و بیمه می‌نامد و ششم صریح تکرار می‌کند؛ اول تا چهارم و هشتم ترتیب شش حوزه را تأیید می‌کنند. نهم چارچوب پژوهشی چهار حوزه است و جای ترتیب چارچوب آموزشی سؤال قرار نگرفته است.',[[(0,'این می‌شود سرفصل پنجم: «مدیریت ریسک و بیمه».','شماره و نام سرفصل مستقیم‌اند.')]])
    b=decision(688,'تمام ده شاهد خوانده شد. صفر مقایسه امروز و گذشته را قدرت غیررسمی و شبکه و نفوذ بیان می‌کند؛ اول ساختار شبکه و روابط در برابر سلسله‌مراتب را شرح می‌دهد. پاسخ نیاز بیشتر است نه حذف قدرت رسمی یا برتری همگانی جنسیتی. خلاقیت و فناوری و اطلاعات مشتری در دیگر شواهد نیازهای دیگری‌اند؛ انحصار سه عامل ادعا نشده است.',[[(0,'و کسب‌وکارهای امروز هم بیشتر از گذشته به قدرت غیررسمی، شبکه و نفوذ نیاز دارن.','مقایسه زمانی و هر سه عامل صریح‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==902
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0052';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[687,688],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0052/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=108,total_reviewed=904,remaining=245,next_position=689)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_687_688_v1',[687,688],'دو KEEP687 و688؛ ادامه689.',cp['created_utc'])
