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
    a=decision(361,'تمام ده شاهد خوانده شد. صفر تنوع‌بخشی و نچیدن همه تخم‌مرغ‌ها در یک سبد را راهبرد کاهش ریسک می‌گوید؛ دوم، چهارم، پنجم، ششم و هشتم مؤیدند. سوم و هفتم تمرکز در حوزه شناخته‌شده را هم راهبرد می‌دانند و ششم تنوع را جادو نمی‌نامد. پاسخ هدف تنوع را کاهش ریسک می‌داند و آن را تنها راهبرد، حذف ریسک یا تضمین سود نمی‌نامد؛ ادعای مطلق هیچ حرفه‌ای متمرکز نیست از صفر به پاسخ منتقل نشده است.',[[(0,'این تکنیک‌هایی که کاهش ریسک در بازار سرمایه هست، معمولاً آدم‌ها آشنا هستن. مثلاً یکی از راهبردهای اصلیش همون تنوع‌بخشیه. همین که تخم‌مرغ‌ها رو همه رو توی یه سبد نذار. یعنی من برم سهام‌های متفاوتی بخرم تو اون سبد، در واقع پرتفوی سرمایه‌گذاریم.','هدف کاهش ریسک و پراکندگی در چند گزینه به جای همه در یک سبد مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'هدف و روش تنوع در صفر مستقیم و چند شاهد دیگر مؤیدند.',
      'question_answer_fit':'هدف اصلی تنوع‌بخشی پاسخ داده شد.',
      'factual_claim_support':'claim واحد کاهش ریسک و قرار ندادن همه در یک گزینه را پوشش دارد.',
      'scope_modality_negation_quantity':'کاهش است نه حذف ریسک یا تضمین بازده؛ تنها راهبرد معرفی نشده.',
      'outside_details':'ترکیب سبد، نسبت تخصیص یا سهم پیشنهادی بیرونی ندارد.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'تمرکز در صنعت شناخته‌شده در سوم و هفتم بدیل یا مکمل است؛ ادعای مطلق حرفه‌ای‌ها در صفر با آن تنش دارد اما پاسخ چنین ادعایی ندارد. هشدار تنوع بدون شناخت در ششم ثبت است.'})
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[361]['response'])
    r['answer_text']='در چارچوب این متن، حوزه‌ها عبارت‌اند از خرج و پس‌انداز، اعتبار و بدهی، کار و درآمد، سرمایه‌گذاری، مدیریت ریسک و بیمه، و تصمیم‌گیری مالی؛ ابعاد سواد مالی هم نگرش، دانش و مهارت‌اند.'
    r['claims'][0]['claim_text']=r['answer_text']
    b=decision(362,'تمام ده شاهد خوانده شد. پاسخ اولیه ابعاد نگرش و دانش و مهارت را می‌گفت اما حوزه‌های موضوعی سؤال را که صفر و چند شاهد مستقیم نام می‌برند حذف می‌کرد. پاسخ با شش حوزه و تفکیک ابعاد تکمیل و claim فعال با دو جمله صفر دوباره بررسی شد. چارچوب پژوهشی چهارحوزه‌ای در هشتم ساختار دیگری است، بنابراین شش حوزه به چارچوب همین متن مقید شد؛ چهار حوزه رشد انسان در ششم و هفتم موضوع دیگری‌اند.',[[(0,'سبک زندگی مالی را می‌توان در شش حوزه دید: خرج و پس‌انداز؛ اعتبار و بدهی؛ کار و درآمد؛ سرمایه‌گذاری؛ مدیریت ریسک و بیمه؛ و در نهایت تصمیم‌گیری مالی که همه حوزه‌های قبلی را دربرمی‌گیرد.','تمام شش حوزه موضوعی در این چارچوب صریح‌اند.'),(0,'در مجموع می‌توانیم بگوییم سواد مالی شامل نگرش‌ها، دانش‌ها و مهارت‌هاست.','سه بعد قبلی پاسخ مستقیم‌اند و از حوزه‌های موضوعی جدا گزارش شده‌اند.')]],repair=r,dimensions={
      'evidence_sufficiency':'شش حوزه و سه بعد هر دو در صفر مستقیم‌اند.',
      'question_answer_fit':'حوزه‌های حذف‌شده تکمیل و با ابعاد قبلی تفکیک شد.',
      'factual_claim_support':'claim فعال هر شش حوزه و هر سه بعد پاسخ را پوشش دارد.',
      'scope_modality_negation_quantity':'شش حوزه مربوط به چارچوب این متن است؛ استاندارد یکتای همه پژوهش‌ها نیست.',
      'outside_details':'اعتبار استاندارد رسمی یا حوزه فرضی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'هشتم چهارحوزه‌ای پژوهشی دارد؛ قید چارچوب متن پاسخ را محدود می‌کند. حوزه‌های رشد معنایی و جسمی با سرفصل‌های مالی خلط نشده‌اند.'})
    b['audit']['error_categories']=['incomplete question coverage','dimensions versus domains']
    b['repair']['reason_fa']='حوزه‌های موضوعی با سه بعد جایگزین شده بودند؛ شش حوزه با قید چارچوب افزوده و ابعاد جدا شدند.'
    b['repair']['recheck_reason_fa']='همه شش نام و هر سه بعد با صفر دوباره تطبیق شدند و اختلاف چارچوب هشتم ثبت شد.'
    c=decision(363,'تمام ده شاهد خوانده شد. صفر پیام سواد مالی را چگونگی مدیریت هر مقدار دخل موجود برای خرج و کیفیت زندگی می‌گوید و ششم مدیریت دخل‌وخرج در حال و آینده را هدف پایه می‌داند. پاسخ همین هسته را خلاصه می‌کند؛ انحصار کل سواد مالی در درآمد یا نفی پس‌انداز و رابطه با پول نیست. پنجم و نهم رابطه فرد با پول را نیز موضوع می‌دانند که با مدیریت آن ناسازگار نیست؛ موفقیت و ثروت تضمین نشده است.',[[(0,'سواد مالی می‌گوید که آقا، هرچقدر دخل داری، چطور مدیریتش بکنی، چطور خرجش بکنی که بهترین کیفیت زندگی را داشته باشی','هسته پیام درباره چگونگی مدیریت دخل موجود مستقیم آمده است.')]],dimensions={
      'evidence_sufficiency':'صفر چگونگی مدیریت دخل را مستقیم می‌گوید و ششم هدف پایه را تأیید می‌کند.',
      'question_answer_fit':'پیام پایه سواد مالی در شرح متن پاسخ داده شد.',
      'factual_claim_support':'claim واحد کل مدیریت درآمد موجود در پاسخ را پوشش دارد.',
      'scope_modality_negation_quantity':'مدیریت هر مقدار درآمد است؛ تضمین ثروتمندی یا انحصار همه مباحث نیست.',
      'outside_details':'درصد خرج، روش درآمدزایی یا نتیجه قطعی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'رابطه با پول و حوزه‌های دیگر در شواهد مکمل‌اند؛ پاسخ آنها را نفی نکرده است.'})
    return [a,b,c]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==842
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0020';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[361,362,363],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0020/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=49,total_reviewed=845,remaining=304,next_position=364)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_361_363_v1',[361,362,363],'دو KEEP و تکمیل حوزه‌های362؛ ادامه364.',cp['created_utc'])
