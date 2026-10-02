"""Explicit full-evidence review for positions 322–324."""
import sys,copy,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'parallel_v1/shared'))
from decisions_006_010 import decision
from audit_structure import rows,save,sha
import incremental_review as frozen
import range_io

def decisions():
    d322=decision(322,'هر ده شاهد خوانده شد. شاهد صفر بیشتر بودن هزینه از درآمد را عقب‌افتادن مالی و هشدار می‌نامد و صریحاً آن را الزاماً ورشکستگی نمی‌داند؛ مصرف سرمایه اولیه را احتمال توضیح‌دهنده مطرح می‌کند. پاسخ احتمال را با ممکن است نگه داشته و ناترازی دخل‌وخرج را با نابرابری معادله ترازنامه خلط نمی‌کند. شواهد قرض و مصرف درآمد آینده راه‌های دیگر تأمین فاصله‌اند؛ پاسخ مصرف سرمایه را تنها علت یا نتیجه قطعی نمی‌داند.',[[
      (0,'اگر که هزینه‌هاتون بیش از درآمد شما باشه، عملاً یعنی شما عقبید از زندگی. این که عقبید از زندگی لزوماً به معنی این نیست که ورشکست شدید. چرا؟ چون که ممکنه یک سرمایه اولیه داشتید و مرتباً\nدارید از اون می‌خورید.','بیشتر بودن هزینه از درآمد و احتمال مصرف سرمایه به جای ورشکستگی قطعی تصریح شده است.'),
      (0,'از سرمایه می‌خورید، دقیقاً. دارید از سرمایه می‌خورید و این یه هشدارِ، این یه خطره.','تعبیر هشدار مالی در همان توضیح مصرف سرمایه آمده است.')]],dimensions={
      'evidence_sufficiency':'توضیح هشدار و احتمال مصرف سرمایه در شاهد صفر کامل است.',
      'question_answer_fit':'معنای اضافه‌هزینه نسبت به درآمد بیان شده؛ توصیه خرید یا افزایش قرض داده نشده.',
      'factual_claim_support':'claim واحد ناترازی، هشدار و احتمال مصرف سرمایه را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'ممکن است حفظ شده؛ ورشکستگی قطعی یا لزوم مصرف سرمایه ادعا نشده.',
      'outside_details':'درصد کسری، حکم ورشکستگی و قانون بیرونی افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'ناترازی مربوط به جریان دخل‌وخرج است، نه معادله دارایی برابر بدهی و سرمایه؛ شواهد مصرف درآمد آینده تعارض ندارند.'})
    d323=decision(323,'هر ده شاهد خوانده شد. شاهد صفر پنج مهارت حوزه هوش عاطفی را برمی‌شمرد: شناخت احساس خود، مدیریت آن، انگیزش خود، شناخت احساس دیگران و مدیریت روابط. پاسخ دو مهارت اول را در یک عبارت ترکیب کرده و سه مهارت بعدی را حفظ کرده است؛ هوش عاطفی را با هوش مالی، شناختی یا معنوی یکی نمی‌کند. شواهد دیگر همین شناخت و مدیریت را تأیید می‌کنند؛ نتایج موفقیت مالی یا امیدواری خارج از تعریف به پاسخ اضافه نشده‌اند.',[[
      (0,'مهارت‌هایی مثل شناخت احساسات خود، مدیریت احساسات خود، برانگیختن و انگیزه‌دادن به خود، شناخت احساسات دیگران و مدیریت روابط با دیگران در این حوزه قرار می‌گیرد.','همه پنج مؤلفه پاسخ در این فهرست آمده‌اند؛ ترکیب شناخت و مدیریت خود دو مؤلفه را حذف نمی‌کند.')]],dimensions={
      'evidence_sufficiency':'فهرست مهارت‌های حوزه هوش عاطفی در شاهد صفر صریح است.',
      'question_answer_fit':'تعریف کوتاه از مهارت‌های اصلی حوزه ارائه شده است.',
      'factual_claim_support':'claim واحد تمام اجزای فهرست متن پاسخ را دارد.',
      'scope_modality_negation_quantity':'فهرست مؤلفه‌هاست؛ تضمین موفقیت یا انحصار در نظریه‌ای خاص ادعا نشده.',
      'outside_details':'نام کتاب، آمار، درمان یا ادعای بیرونی به تعریف اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'تعریف شناخت و مدیریت احساسات خود و دیگران در شاهد دوم با فهرست پنج‌گانه سازگار است؛ حوزه‌های هوش دیگر جدا مانده‌اند.'})
    d324=decision(324,'هر ده شاهد خوانده شد. شاهد صفر زیر عنوان عمق‌بخشی به رزومه تجربه کار داوطلبانه را تجربه حرفه‌ای می‌نامد و امکان ثبت سازمان، مدت و مسئولیت را توضیح می‌دهد. پاسخ همین اثر بر رزومه را بیان کرده؛ وعده استخدام، حقوق یا رضایت همه کارفرمایان اضافه نشده. شواهد چندگانه تقویت رزومه مؤیدند؛ هشدار بی‌ثباتی شغلی بعد از فارغ‌التحصیلی اثر ثبت تجربه واقعی داوطلبانه را نفی نمی‌کند.',[[
      (0,'عمق‌بخشی به رزومه:\nتجربه کار داوطلبانه هم یک تجربه حرفه‌ای محسوب می‌شود بنابراین می‌توانید نام آن سازمان و تاریخ و مدت خدمتتان را در رزومه خود عنوان کنید.','عنوان عمق‌بخشی و حرفه‌ای بودن تجربه داوطلبانه هر دو جزء پاسخ را مستقیم پشتیبانی می‌کنند.')]],dimensions={
      'evidence_sufficiency':'عنوان و توضیح تجربه حرفه‌ای در شاهد صفر کافی است.',
      'question_answer_fit':'اثر کار داوطلبانه بر رزومه، نه دیگر مزایای کار، پاسخ داده شده.',
      'factual_claim_support':'claim واحد هر دو گزاره تجربه حرفه‌ای و عمق رزومه را دارد.',
      'scope_modality_negation_quantity':'تقویت رزومه به تضمین استخدام یا برتری بر همه متقاضیان تبدیل نشده.',
      'outside_details':'سابقه بیمه، مزایای قانونی و مبلغ حقوق افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'هشدار تغییر مکرر شغل پس از فارغ‌التحصیلی، ثبت تجربه داوطلبانه را رد نمی‌کند؛ سایر شواهد تقویت رزومه را تکرار می‌کنند.'})
    return [d322,d323,d324]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==803
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0004';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[322,323,324],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0004/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=10,total_reviewed=806,remaining=343,next_position=325)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_322_324_v1',[322,323,324],'سه KEEP جدید 322–324؛ delta کوچک coordinator/resume_v1؛ پوشش کل این نوبت 315–324.',cp['created_utc'])
