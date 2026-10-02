"""Explicit AGENT_REVIEW after reading all twenty evidence texts."""
import sys,json,copy
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'parallel_v1/shared'))
from decisions_006_010 import decision
from audit_structure import rows,save,sha
import incremental_review as frozen
import range_io

def decisions():
    a=decision(326,'هر ده شاهد خوانده شد. شاهد صفر سبک چهارم را پیمانکاری و گرفتن و انجام پروژه از ابتدا تا انتها معرفی می‌کند. شواهد یک، دو و شش نیز همین جایگاه چهارم را در طبقه‌بندی پنج‌گانه رابطه کار و درآمد دارند؛ ترتیب سه سبک نخست در بعضی شواهد متفاوت است اما چهارم ثابت است. شاهد سوم و هفتم درباره رویکرد چهارم به شغل و زیست یکپارچه‌اند، نه سبک درآمدی؛ با سؤال نوع سبک شغلی و تعریف پروژه خلط نشده‌اند.',[[
      (0,'خب چهارومین نوع سبک شغلی پیمانکاری\nیعنی چی؟\nیعنی من یک پروژهی رو می‌گیرم\nاز اول تا آخرشو انجام میدم و پولشو می‌گیرم','ترتیب چهارم، نام پیمانکاری و اجرای کامل پروژه همگی مستقیم آمده‌اند.')]],dimensions={
      'evidence_sufficiency':'تعریف و ترتیب سبک چهارم در شاهد صفر صریح است و سه شاهد دیگر مؤیدند.',
      'question_answer_fit':'پیمانکاری همراه با معنای پروژه از آغاز تا پایان پاسخ همان سبک چهارم است.',
      'factual_claim_support':'claim واحد تمام نام و تعریف پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'چهارم در طبقه‌بندی پنج سبک رابطه کار و درآمد است؛ نه چهارمین رویکرد معنایی به شغل.',
      'outside_details':'تعهد حقوقی، تضمین دستمزد یا انواع قرارداد بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'تفاوت ترتیب استخدام و کارفرمایی در ابتدا بر چهارم اثر ندارد؛ رویکرد زیست یکپارچه طبقه‌بندی جداست.'})
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[326]['response']);ev=json.loads(rows(ROOT/'inputs.jsonl')[326]['messages'][1]['content'])['evidence']
    r['answer_text']='اینها گزارش‌های حسابداری‌اند؛ ترازنامه وضعیت مالی را در یک لحظه نشان می‌دهد و صورت‌حساب سود و زیان، درآمد و هزینه و سود یا زیان یک دوره را نشان می‌دهد.'
    r['claims'][0]['claim_text']='ترازنامه و صورت‌حساب سود و زیان گزارش‌های حسابداری‌اند و ترازنامه وضعیت مالی را در یک لحظه نشان می‌دهد.'
    r['claims'].append(dict(claim_text='صورت‌حساب سود و زیان درآمد و هزینه و سود یا زیان یک دوره را نشان می‌دهد.',claim_type='FACTUAL',evidence_ids=[ev[6]['evidence_id']]))
    b=decision(327,'تمام ده شاهد خوانده شد. پاسخ اصلی طبقه گزارش حسابداری و نقش ترازنامه را داشت اما نقش صورت سود و زیان را در سؤال دوگانه توضیح نمی‌داد. با شاهد ششم درآمد و هزینه و سود یا زیان یک دوره افزوده و claim مستقل برای آن ثبت شد. پاسخ فعال دوباره با شاهد صفر و ششم و شرح دوره زمانی در شاهد سوم تطبیق شد. شاهد نهم اصطلاح ترازنامه را برای درآمد و هزینه به‌صورت ناسازگار به کار می‌برد؛ این اختلاف ثبت شده و پاسخ از شرح صریح و چندشاهدی دو گزارش استفاده می‌کند، نه عبارت مختلط نهم. سود حسابداری با نقد موجود یکی نشده است.',[
      [(0,'یکی ترازنامه هست، یکی صورت‌حساب سود و زیانه','در مقدمه گزارش‌های حسابداری هر دو نام برده شده‌اند.'),
       (0,'ترازنامه به شما می‌گه که شما چه وضعیت مالی دارید در هر لحظه از طول زندگیتون.','نقش وضعیت مالی لحظه‌ای مستقیم تصریح شده است.')],
      [(6,'درآمدهای یک دوره رو می‌نویسیم، هزینه‌ها رو کم می‌کنیم و سود یا زیان رو می‌بینیم. به این می‌گن **صورت سود و زیان**.','درآمد، هزینه، سود یا زیان و بازه دوره همگی در تعریف همین صورت آمده‌اند.')]],repair=r,dimensions={
      'evidence_sufficiency':'شاهد صفر برای طبقه و نقش ترازنامه و شاهد ششم برای صورت سود و زیان کافی‌اند.',
      'question_answer_fit':'نقش هر دو گزارش پس از رفع حذف نیمه دوم سؤال پوشش یافت.',
      'factual_claim_support':'دو claim فعال تمام دو بخش متن پاسخ را پوشش دارند.',
      'scope_modality_negation_quantity':'ترازنامه لحظه و سود و زیان دوره است؛ نه اینکه سود همان وجه نقد موجود باشد.',
      'outside_details':'استاندارد حسابداری، مقررات مالیاتی یا اقلام بی‌شاهد اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'نام‌گذاری مختلط درآمد و هزینه به ترازنامه در شاهد نهم با شرح صریح صفر، یک، دو، سه و ششم ناسازگار است؛ تعریف صریح چندشاهدی مبنای پاسخ محدود است.'})
    b['audit']['error_categories']=['incomplete question coverage']
    b['repair']['reason_fa']='نقش صورت سود و زیان از پاسخ سؤال دوگانه حذف شده بود؛ متن و claim مستقل با شاهد ششم تکمیل شدند.'
    b['repair']['recheck_reason_fa']='پس از اصلاح، دو گزارش، وضعیت لحظه‌ای و درآمد و هزینه و نتیجه یک دوره با شواهد صفر و ششم دوباره بررسی شد؛ اختلاف اصطلاح نهم و تمایز نقد و سود ثبت شدند.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==807
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0006';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[326,327],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0006/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=13,total_reviewed=809,remaining=340,next_position=328)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_326_327_v1',[326,327],'326 حفظ و327 با تکمیل نقش صورت سود و زیان اصلاح و بازبینی شد؛ ادامه328.',cp['created_utc'])
