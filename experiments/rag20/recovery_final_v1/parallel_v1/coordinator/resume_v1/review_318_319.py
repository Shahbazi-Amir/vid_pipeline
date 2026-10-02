"""Explicit reviewed decisions; no generated semantic checks."""
import sys,copy,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'parallel_v1/shared'))
from decisions_006_010 import decision
from audit_structure import rows,save,sha
import incremental_review as frozen
import range_io

def decisions():
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[317]['response'])
    r['answer_text']='به ۲۴ عبارت، بر اساس میزان موافقت یا مخالفت، امتیاز یک تا پنج بدهید؛ برای هر امتیاز روی نمودار رادار نقطه بگذارید و سپس نقاط را به هم وصل کنید.'
    r['claims'][0]['claim_text']=r['answer_text']
    d318=decision(318,'تمام ده شاهد خوانده شد. شاهد صفر علاوه بر امتیازدهی به ۲۴ عبارت و گذاشتن نقطه، وصل‌کردن نقاط را مرحله مهم بعدی می‌داند. پاسخ اصلی دو مرحله اول را داشت اما مرحله وصل‌کردن نقاط را برای تکمیل شکل جا انداخته بود. پاسخ و claim با حفظ تعداد و دامنه یک تا پنج تکمیل شدند. متن فعال دوباره با شاهد تطبیق شد؛ ضرورت دایره کامل یا سلامت روان و زمان الزامی سه دقیقه ادعا نشده. اشاره شش‌وجهی شاهد نهم موضوع دیگری است و تعداد ۲۴ عبارت این کاربرگ را تغییر نمی‌دهد.',[[
      (0,'ببینید اینجا 24 تا عبارت نوشته شده\nبسته به این که شما موافقش هستید یا مخالفش\nبین یک تا پنج یعنی عدد بهش اختصاص میدید','تعداد ۲۴ و مبنای میزان موافقت و مخالفت و دامنه یک تا پنج برای امتیازدهی صریح است.'),
      (0,'این نمودار رادار رو تکمیل کنید و به ازای هر کدوم از این عبارتها یه نقطه بذارید','گذاشتن نقطه برای هر عبارت، مرحله رسم امتیازها را پشتیبانی می‌کند.'),
      (0,'حالا یه کار مهم باید انجام بدید\nاین نقاط رو به هم وصل کنید','مرحله اتصال نقاط که در نسخه اولیه حذف شده بود، به صراحت دستور داده شده است.')]],repair=r,dimensions={
      'evidence_sufficiency':'دستور امتیازدهی، نقطه‌گذاری و اتصال همگی در شاهد صفر موجودند.',
      'question_answer_fit':'نقص مرحله تکمیل شکل با افزودن وصل‌کردن نقاط رفع شد.',
      'factual_claim_support':'claim فعال هر سه مرحله و تعداد و دامنه امتیازها را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'۲۴ عبارت و امتیاز ۱ تا ۵ حفظ شد؛ دایره کامل یا تفسیر وضع سواد مالی ادعا نشده.',
      'outside_details':'روش جدید محاسبه، نرم‌افزار یا نمودار شش‌وجهی دیگری اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'رادار شش‌وجهی شاهد نهم مربوط به کار و درآمد است؛ با کاربرگ ۲۴عبارتی شاهد صفر خلط نشده.'})
    d318['audit']['error_categories']=['incomplete procedural answer']
    d318['repair']['reason_fa']='مرحله اتصال نقاط برای تکمیل نمودار حذف شده بود؛ answer_text و claim با افزودن آن تکمیل شدند.'
    d318['repair']['recheck_reason_fa']='پس از اصلاح، هر سه مرحله امتیازدهی ۲۴ عبارت از ۱ تا ۵، نقطه‌گذاری و اتصال نقاط دوباره با شاهد صفر بررسی شد؛ هیچ شرط یا نتیجه بی‌شاهد در پاسخ فعال نیست.'
    d319=decision(319,'تمام ده شاهد خوانده شد. شاهد صفر بازی، بیان استعاری و تصویر را ابزار استفاده همزمان از دو نیمکره معرفی می‌کند. پاسخ با «ابزارهای مطرح‌شده در متن» فقط این فهرست را گزارش می‌کند و تقسیم نقش نیمکره راست و چپ یا صحت مستقل عصب‌شناسی متن را تکرار نمی‌کند. مثال سینما و تصویرسازی در سایر شواهد با فهرست تعارض ندارد؛ پاسخ فهرست را انحصاری نمی‌نامد.',[[
      (0,'ابزارهایی مانند بازی که هیجان و احساس را در خود دارد یا بیان استعاری که تخیل را درگیر می کند یا تصویر که ذخیره دانش را در ذهن ساده‌تر می‌کند، همه کمک به همین ماجرای استفاه همزمان از دو نیمکره مغز است.','هر سه ابزار و کارکرد مورد سؤال در یک جمله تصریح شده؛ «مانند» شاهد با فهرست نمونه‌ها در پاسخ حفظ شده و صحت مستقل نقش نیمکره‌ها ادعا نشده.')]],dimensions={
      'evidence_sufficiency':'فهرست نمونه ابزارها مستقیماً در شاهد صفر آمده است.',
      'question_answer_fit':'سه ابزار سؤال با انتساب به متن بیان شده‌اند.',
      'factual_claim_support':'claim واحد هر سه عضو فهرست و انتساب به متن را پوشش دارد.',
      'scope_modality_negation_quantity':'فهرست مثال‌هاست؛ تنها ابزارهای ممکن یا تقسیم قطعی نقش نیمکره‌ها ادعا نشده.',
      'outside_details':'هیچ ادعای عصب‌شناسی یا اثربخشی بیرون از متن اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'تقسیم نقش نیمکره‌ها در مقدمه شاهد در پاسخ بازنشر نشده؛ ممیزی، entailment در همان متن را می‌سنجد و صحت علمی مستقل آن NOT_EVALUATED است.'})
    return [d318,d319]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==799
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0002';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[318,319],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    reloaded=rows(directory/'decisions.jsonl');assert frozen.validate(frozen.append_decisions(previous,reloaded),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0002/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=5,total_reviewed=801,remaining=348,next_position=320)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_318_319_v1',[318,319],'دو مورد جدید؛ 318 با تکمیل اتصال نقاط اصلاح و بازبینی شد؛ delta کوچک coordinator/resume_v1.',cp['created_utc'])
