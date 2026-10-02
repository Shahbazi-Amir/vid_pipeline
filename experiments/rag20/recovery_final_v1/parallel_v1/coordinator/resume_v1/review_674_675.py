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
    a=decision(674,'تمام ده شاهد خوانده شد. صفر پذیرش سختی رشته به دلیل علاقه و صرف انرژی برای کار را مستقیم می‌گوید؛ چهارم کار بهتر و درست‌تر و ششم انجام کارهای نامحبوب در مسیر علاقه را تأیید می‌کنند. پاسخ فقط تحمل سختی و تلاش است، تضمین موفقیت یا کافی بودن علاقه و حذف استعداد و نیاز جامعه نیست.',[[(0,'ولی کسی که علاقه‌مند به یه رشته باشه تمام اون سختی‌ها رو به جون می‌خره.','تحمل سختی به دلیل علاقه مستقیم است.'),(0,'خانم‌ها اگر به کار علاقه داشته باشن همه انرژی خودشون رو برای اون کار می‌ذارن','تلاش به دلیل علاقه در مثال متن صریح است.')]])
    b=decision(675,'تمام ده شاهد خوانده شد. صفر چهار اقدام کاهش ریسک سرقت طلا را فهرست می‌کند. اول حفظ اطلاعات و چهارم گاوصندوق و پراکندگی دارایی پیشنهادهای دیگرند؛ پاسخ اقدامات نمونه می‌گوید نه فهرست انحصاری. هشتم بیمه انتقال هزینه خسارت است، با کاهش احتمال سرقت خلط نشده؛ تضمین نبود سرقت هم نیست.',[[(0,'می\u200cگیم که ریسک طلا سرقت بود دیگه. می\u200cگم طلا می\u200cخرم ولی درِ آکاردئونی جلو آپارتمانم می\u200cزنم، نرده دور آپارتمان رو تکمیل\nمی\u200cکنم، دزدگیر می\u200cذارم یا توی صندوق امانات\nمی\u200cذارم.','هر چهار اقدام حفاظت در و نرده و دزدگیر و صندوق برای کاهش ریسک طلا مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==889
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0046';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[674,675],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0046/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=95,total_reviewed=891,remaining=258,next_position=676)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_674_675_v1',[674,675],'دو KEEP674 و675؛ ادامه676.',cp['created_utc'])
