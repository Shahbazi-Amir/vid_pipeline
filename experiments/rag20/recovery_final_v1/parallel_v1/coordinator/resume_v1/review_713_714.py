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
    a=decision(713,'تمام ده شاهد خوانده شد. صفر تعریف نقل‌شده کار سبک با کمتر از۱۴ ساعت و نبود آسیب و مانع آموزش را دارد و اول کامل تکرار می‌کند. هفتم چارچوب برنامه تربیتی را با سقف۲۱ ساعت بیان می‌کند که با عدد تعریف سبک یکسان نیست. پاسخ صریحاً محدود به تعریف نقل‌شده است و قانون جاری جهانی یا مجوز همه سنین معرفی نمی‌کند.',[[(0,'بر اساس همین تعریف کار سبک (برابر کار پر خطر) که به رشد جسمی و اخلاقی آن‌ها آسیب نمی‌زند و دسترسی آن‌ها را به مدرسه و برنامه آموزشی محدود نمی‌کند و کمتر از 14 ساعت در هفته است،','هر سه شرط در تعریف نقل‌شده مستقیم است.')]])
    b=decision(714,'تمام ده شاهد خوانده شد. صفر گزینه د پرسشنامه واکنش به افت۲۰ درصد طی سه ماه از سرمایه‌گذاری دوساله را بیان می‌کند. گزینه آزمون را نباید توصیه عمومی خرید هنگام هر افت دانست. چهارم و نهم حدضرر و سایر شواهد ریسک و حفظ ارزش را دارند و تضمین سود در کل مجموعه نیست. پاسخ جایگاه گزینه پرسشنامه را درست حفظ کرده است.',[[(0,'د) با توجه به کاهش ارزش آن، فرصت خوبی برای سرمایه‌گذاری بیشتر است','یکی از چهار گزینه پرسشنامه است.')]],units=[dict(text='در پرسشنامه، سرمایه‌گذاری بیشتر پس از کاهش ارزش به‌عنوان یکی از گزینه‌های واکنش آمده است؛',kind='FACTUAL',claim_indices=[0],reason_fa='گزینه پرسشنامه'),dict(text=' متن آن را حکم عمومی یا تضمین سود معرفی نمی‌کند.',kind='EVIDENCE_LIMITATION',claim_indices=[],reason_fa='قید محدودیت شواهد و نبود تضمین')])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==928
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0065';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[713,714],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0065/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=134,total_reviewed=930,remaining=219,next_position=715)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_713_714_v1',[713,714],'دو KEEP713 و714؛ ادامه715.',cp['created_utc'])
