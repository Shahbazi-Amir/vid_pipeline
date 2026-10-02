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
    a=decision(388,'تمام ده شاهد خوانده شد. صفر بیست پیروزی پیاپی اکلند را در روایت فیلم بازی پول و بازه103سال اخیر همان متن صریح می‌گوید. پاسخ فقط تعداد برد متوالی است و تنها تیم یا رکورد جاری جهان را ادعا نمی‌کند. اول همان داستان را مقدمه می‌چیند؛ سایر شواهد بازی آموزشی، قمار، ورزش، بازار و داستان کودک موضوع دیگری‌اند.',[[(0,'بیست پیروزی پیاپی رکوردی بی‌سابقه در تاریخ بیسبال. اٌکلند در طول صد و سه سال اخیر تنها تیمی است که توانسته این تعداد بازی را پی‌درپی برنده شود.','تعداد بیست در همان بازه مرجع سؤال صریح است؛ ادعای رکورد جاری به پاسخ منتقل نشده است.')]])
    data=json.loads(rows(ROOT/'inputs.jsonl')[388]['messages'][1]['content'])
    answer='طبق متن، با باز کردن حساب بانکی وارد بازار پول می‌شوید؛ امکانات به نوع حساب بستگی دارد و خدماتی مانند انتقال وجه و پرداخت قبض برای حساب‌های توضیح‌داده‌شده ذکر شده است.'
    r=dict(answer_text=answer,claims=[dict(claim_text=answer,claim_type='FACTUAL',evidence_ids=[data['evidence'][i]['evidence_id'] for i in [1,5,7]])])
    b=decision(389,'تمام ده شاهد خوانده شد. پاسخ اولیه امکان بازکردن حساب را نامعلوم می‌گفت اما پنجم ورود به بازار پول را مستقیم بیان می‌کند، اول امکانات را به نوع حساب وابسته می‌داند و هفتم انتقال وجه و پرداخت قبض را نام می‌برد. پاسخ با همان محدوده اصلاح شد. چک برای همه نیست و اعتبار یا اضافه‌برداشت برای هر حساب تضمین نشده؛ متن صفر را به حق خودکار افتتاح حساب تعمیم ندادیم. مانکی و امنیت حساب و کلاهبرداری موضوعات مکمل و مستقل‌اند.',[[(5,'تو بانک وقتی می‌ده یه حساب بانکی باز می‌کنی وارد بازار پول شدی','پیامد بازکردن حساب و ورود بازار پول صریح است.'),(1,'وقتی حساب باز می‌کنیم باید بدانیم چه نوع حسابی است و چه امکاناتی دارد.','وابستگی امکانات به نوع حساب در متن روشن است.'),(7,'قبوضمون رو پرداخت بکنیم\nنمی\u200cدونم وشهامون رو انتقال بدیم','دو مثال خدمات حساب‌ها در متن مستقیم‌اند و پاسخ به حساب‌های توضیح‌داده‌شده محدود است.')]],repair=r)
    b['audit']['error_categories']=['unsupported abstention'];b['repair']['reason_fa']='ورود بازار پول و خدمات مشخص شواهد اول و پنجم و هفتم نادیده مانده بود؛ پاسخ مقید به نوع حساب جایگزین شد.';b['repair']['recheck_reason_fa']='هر سه بخش پاسخ با اول و پنجم و هفتم تطبیق و دریافت خودکار چک یا اعتبار ادعا نشد.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==869
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0036';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[388,389],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0036/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=75,total_reviewed=871,remaining=278,next_position=390)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_388_389_v1',[388,389],'KEEP388 و REPAIRED389؛ ادامه390.',cp['created_utc'])
