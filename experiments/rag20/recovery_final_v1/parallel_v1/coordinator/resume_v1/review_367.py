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
    return [decision(367,'تمام ده شاهد خوانده شد. صفر و اول ترتیب پرداخت اکنون و دریافت کالای آینده را در بیع سلف و ترتیب عکس در نسیه تصریح می‌کنند. پنجم تعریف بانکی پیش‌خرید نقدی و هفتم مثال پیش‌فروش را تأیید می‌کنند. پاسخ تعریف عمومی است و جزئیات جعاله، استصناع، خرید دین یا خرید قسطی را به سلف نسبت نمی‌دهد. خرابی پیاده‌سازی نام اصطلاح در سؤال با تکرار روشن سلف در شواهد رفع می‌شود.',[[(0,'یعنی من اول پول رو میدم\nبعدا کالا رو می\u200cگیرم\nمثل این که تو نسیه اول کالا رو میگیری\nبعد پول رو میدی به یه اسالف برعکسه','هر دو ترتیب پرداخت و تحویل و مقایسه با نسیه مستقیم ذکر شده‌اند.')]])]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==848
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0023';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[367],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0023/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=53,total_reviewed=849,remaining=300,next_position=368)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_367_v1',[367],'KEEP367؛ ادامه368.',cp['created_utc'])
