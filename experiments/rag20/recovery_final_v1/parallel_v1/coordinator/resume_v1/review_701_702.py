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
    a=decision(701,'تمام ده شاهد خوانده شد. صفر انتخاب یک ردیف مانند بدهی و اقساط توسط خانم دارای درآمد را یکی از روش‌های همکاری همسران می‌داند. پاسخ پیشنهاد متن و یکی از روش‌ها را حفظ کرده و الزام قانونی همه زنان به پرداخت بدهی خانواده نیست. ششم مالکیت مستقل زن و پنجم توافق شفاف با این پیشنهاد اختیاری تعارض ندارد؛ سایر توصیه‌ها حذف یا انحصاری دانسته نشده‌اند.',[[(0,'یکی از روش‌های خوب برای ایجاد همکاری مالی بین همسران این است که اگر خانم هم درآمدی دارد، یکی از ردیف‌های بودجه، مثل بدهی و اقساط منزل، را انتخاب کرده و آن را پرداخت کند','شرط درآمد و اختیاری بودن روش و مثال ردیف مستقیم‌اند.')]])
    b=decision(702,'تمام ده شاهد خوانده شد. صفر ماندن مفهوم در ذهن به همراهی تصویر و اتفاق را توضیح می‌دهد؛ اول و پنجم همذات‌پنداری و یادگیری و سوم تجربه انسانی را تأیید می‌کنند. پاسخ کمک به ماندگاری است نه تضمین تبدیل رفتار یا صحت هر داستان؛ خطر شعار و نیاز بررسی تخصصی در صفر با پاسخ تعارض ندارد.',[[(0,'مفهوم در ذهن می‌ماند چون با تصویر و اتفاق همراه شده است.','پیوند تصویر و اتفاق و ماندگاری مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==916
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0059';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[701,702],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0059/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=122,total_reviewed=918,remaining=231,next_position=703)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_701_702_v1',[701,702],'دو KEEP701 و702؛ ادامه703.',cp['created_utc'])
