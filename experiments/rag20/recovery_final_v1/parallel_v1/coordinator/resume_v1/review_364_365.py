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
    a=decision(364,'تمام ده شاهد خوانده شد. صفر و اول و پنجم رویکرد سوم ماورایی را احساس مأموریت الهی یا فراخوان جامعه یا حس درونی می‌دانند. پاسخ با در رویکرد ماورایی دامنه را صریح محدود کرده؛ تعیین هویت صاحب ضمیر نامعلوم یا مأموریت واقعی از بیرون نیست. رویکرد حرفه‌ای و یکپارچه در شواهد تعریف دیگری دارند اما پاسخ به آن رویکردها تعمیم نداده است.',[[(0,'یه روی کرد ماورایی و رؤیاگونه هست\nشغلش براش یه مأموریت الهیه\nمثلا فکر می‌کنه که یک جامعه این رو بردوش اون قرار داده\nیا یه حس درونیه','نام رویکرد و هر سه نوع احساس مأموریت مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر هر سه مأموریت و دامنه رویکرد را مستقیم دارد و دو شاهد مؤیدند.',
      'question_answer_fit':'توضیح محدود به رویکرد ماورایی داده شده، نه تعیین هویت شخص نامعلوم.',
      'factual_claim_support':'claim واحد قید رویکرد و هر سه منشأ مأموریت را پوشش دارد.',
      'scope_modality_negation_quantity':'برای فرد و در رویکرد ماورایی است؛ وجود عینی فراخوان الهی تأیید نشده.',
      'outside_details':'هویت شخص، مأموریت حقیقی یا توصیه انتخاب شغل اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'ضمیرش در سؤال مرجع صریح ندارد؛ قید رویکرد دامنه پاسخ را مشخص می‌کند. رویکرد حرفه‌ای و سبک‌های درآمدی جدا مانده‌اند.'})
    b=decision(365,'تمام ده شاهد خوانده شد. صفر کودک خواستار هر کالای فروشگاه را مثال می‌زند و با شرط تغییر ندادن رفتار، پیامد هزینه هر خواسته در بزرگسالی را هشدار می‌دهد. پاسخ هزینه خواسته‌های مدیریت‌نشده را خلاصه می‌کند؛ بدهکار شدن قطعی، جرم یا ورشکستگی همه کودکان را اضافه نمی‌کند. شواهد والدین، عادت‌ها و تبدیل دانش به عمل مکمل‌اند؛ تغییر پول اسمی و فشار فقر درباره همین رفتار کودک نیستند.',[[(0,'اما اگر رفتارشان را تغییر ندهند، وقت بزرگسالی، دنیای مالی دمار از روزگارشان در می‌آورد. چون تازه آن موقع است که معنی عبارت «هر خواسته‌ای هزینه‌ای دارد» را با گوشت و پوستشان لمس می‌کنند.','شرط عدم تغییر و زمان بزرگسالی و پیامد هزینه خواسته مستقیم‌اند و زبان مبالغه‌آمیز به شرح پیامد مالی محدود شده است.')]],dimensions={
      'evidence_sufficiency':'صفر شرط و پیامد و علت هزینه خواسته را مستقیم دارد.',
      'question_answer_fit':'پیامد تداوم رفتار خواستن همه چیز در بزرگسالی پاسخ داده شد.',
      'factual_claim_support':'claim واحد زمان و پیامد هزینه خواسته‌های مدیریت‌نشده را پوشش دارد.',
      'scope_modality_negation_quantity':'در فرض سؤال عدم تغییر رفتار است؛ همه کودکان یا همه خواسته‌ها الزاماً ورشکست‌کننده نیستند.',
      'outside_details':'بدهی، جرم و رقم خسارت قطعی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'بچه‌ها در صفر کودک خواستار همه محصولات‌اند؛ شواهد تغییر رفتار مالی و آموزش والدین مکمل‌اند و بحث ارزش اسمی موضوع دیگری است.'})
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==845
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0021';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[364,365],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0021/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=51,total_reviewed=847,remaining=302,next_position=366)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_364_365_v1',[364,365],'دو KEEP364 و365؛ ادامه366.',cp['created_utc'])
