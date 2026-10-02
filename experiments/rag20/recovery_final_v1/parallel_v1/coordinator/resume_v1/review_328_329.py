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
    a=decision(328,'تمام ده شاهد خوانده شد. شاهد صفر یک‌سوم جمعیت انگلستان را کاملاً وابسته به اقتصاد می‌نامد و شاهد اول همان ادعا را تکرار می‌کند. پاسخ صریحاً طبق ادعای متن است؛ عدد را آمار فعلی یا تأییدشده بیرونی نمی‌نامد. یک‌سوم ثروتمند، ۳۰درصد ناآگاه از مستمری، ۱۸درصد بدهکار بزرگسال و یک‌سوم باسواد مالی جهان در شواهد دیگر موضوع یا مخرج دیگری دارند و خلط نشده‌اند.',[[
      (0,'همان طور که قبلاً اشاره کردم، یک‌سوم جمعیت انگلستان در واقع هیچ سهمی در اقتصاد کشور ندارند؛ بلکه کاملاً به آن وابسته‌اند.','کمیت یک‌سوم، جمعیت انگلستان و وابستگی کامل در یک جمله ادعای منبع آمده است؛ پاسخ با انتساب گزارش می‌کند.')]],dimensions={
      'evidence_sufficiency':'کمیت و کشور و وابستگی کامل مستقیماً در صفر و اول آمده‌اند.',
      'question_answer_fit':'همان سهم جمعیت کشورِ مورد سؤال با انتساب به متن پاسخ داده شده.',
      'factual_claim_support':'claim واحد عدد و انتساب متن پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'یک‌سوم کل جمعیت انگلستان در ادعای متن است؛ نه جمعیت بزرگسال، فقرا در جهان یا آمار جاری.',
      'outside_details':'تاریخ، رقم جمعیت و آمار فعلی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'مقادیر کشورهای دیگر و شاخص‌های بدهی و سواد مالی درباره همین متغیر نیستند؛ صحت مستقل ادعای جمعیتی NOT_EVALUATED است.'})
    b=decision(329,'تمام ده شاهد خوانده شد. شاهد صفر نگرانی مالی را رابطه ما با پول و مفهوم روان‌شناختی آن در اندیشه و احساس و رفتار می‌داند. پاسخ همین تعریف را خلاصه می‌کند، بدون اینکه همه اضطراب‌ها را بیماری بداند یا فشار واقعی مالی را انکار کند. شواهد یک و دو مؤید تعریف‌اند؛ شواهد اقساط و مسکن از آمیختگی نگرانی و مسئله و ضرورت تبدیل آن به مسئله سخن می‌گویند و تعریف مورد سؤال را نقض نمی‌کنند.',[[
      (0,'نگرانی مالی دربارۀ رابطۀ ما با پول است.','موضوع نگرانی مالی در تعریف منبع، رابطه فرد با پول است.'),
      (0,'از دیدگاه اقتصادی، پول بی‌طرف است؛ اما از دیدگاه روان‌شناختی، پول برای هر کس مفهومی دارد که در اندیشه و احساس و در نتیجه، رفتار او اثر می‌گذارد.','معنایی که فرد به پول می‌دهد جزء روان‌شناختی همان رابطه است؛ پاسخ آن را با مقدار اسکناس یکی نکرده است.')]],dimensions={
      'evidence_sufficiency':'موضوع رابطه و معنای فردی در شاهد صفر مستقیم است.',
      'question_answer_fit':'تعریف موضوع نگرانی مالی ارائه شد، نه راهکار درآمد یا حل بدهی.',
      'factual_claim_support':'هر دو جزء رابطه فرد و معنای پول با claim و دو span پوشش دارند.',
      'scope_modality_negation_quantity':'تعریف نگرانی در این درس است؛ انکار همه عوامل اقتصادی یا حکم پزشکی همگانی ندارد.',
      'outside_details':'تشخیص روان‌پزشکی، علت زیستی یا نسخه درمان اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'تفاوت مسئله دخل‌وخرج و نگرانی رابطه‌ای حفظ شده؛ مثال‌های مسکن و قسط در شواهد به زمینه نگرانی اشاره دارند.'})
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==809
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0007';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[328,329],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0007/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=15,total_reviewed=811,remaining=338,next_position=330)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_328_329_v1',[328,329],'دو KEEP جدید328 و329؛ ادامه330.',cp['created_utc'])
