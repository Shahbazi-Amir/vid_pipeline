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
    a=decision(721,'تمام ده شاهد خوانده شد. صفر نتیجه مطالعه نقل‌شده آموزش دانش‌آموزان پرو و سرریز به والدین را صریح بیان می‌کند. سایر شواهد بیشتر مسیر والدین به کودک و مکمل بودن مدرسه و خانواده‌اند. پاسخ طبق مطالعه نقل‌شده می‌گوید و به همه کشورها یا تضمین تغییر همه والدین تعمیم نداده است.',[[(0,'این مطالعه نشان می‌دهد که دانش‌آموزان ظرفیت بالایی برای انتقال اطلاعات به خانواده و تأثیرگذاری بر والدین دارند و آموزش سواد مالی در مدارس روشی مقرون‌به‌صرفه برای دسترسی و آموزش به بزرگ‌سالان است.','ظرفیت و جهت انتقال در مطالعه مستقیم است.')]])
    b=decision(722,'تمام ده شاهد خوانده شد. صفر سرمایه‌گذاری مناسب و اتصال به بخش واقعی اقتصاد را یکی از راه‌های مراقبت ارزش می‌داند. دوم امکان زیان و ابزار متناسب با ریسک و نقدشوندگی، پنجم دارایی مولد و ششم فعالیت واقعی و نهم هدف صندوق‌ها را توضیح می‌دهند. پاسخ اقدام با سرمایه‌گذاری مناسب برای مراقبت ارزش است و میزان سود یا تضمین حفظ قدرت خرید وعده نمی‌دهد.',[[(0,'پس یکی از مهم‌ترین کارهایی که باید در نگهداری پول انجام بدهیم، مراقبت از ارزش آن است. یکی از راه‌های این مراقبت، به‌کارانداختن پول و متصل‌کردن آن به بخش واقعی اقتصاد از طریق سرمایه‌گذاری مناسب است.','اقدام و هدف مراقبت ارزش مستقیم بیان شده است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==936
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0069';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[721,722],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0069/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=142,total_reviewed=938,remaining=211,next_position=723)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_721_722_v1',[721,722],'دو KEEP721 و722؛ ادامه723.',cp['created_utc'])
