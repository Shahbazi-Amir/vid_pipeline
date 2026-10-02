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
    a=decision(339,'تمام ده شاهد خوانده شد. صفر در یک قیاس هر دو بخش سؤال را مستقیم پاسخ می‌دهد: احتیاط راننده در جاده بد و شناخت تکلیف مالیاتی با وجود ایراد اجرای آن. سایر شواهد رانندگی نقش واکنش فرد را توضیح می‌دهند و اثر شرایط بیرونی را نفی نمی‌کنند. پاسخ حکم کشور یا مالیات و جرایم امروز را تعیین نمی‌کند و ناآگاهی را موجب سلب قطعی همه حقوق فرد نمی‌نامد؛ فقط مضمون همین متن را خلاصه می‌کند.',[[(0,'فارغ از کیفیت سیاست‌گذاری کلان، فرد و خانواده باید تکلیف مالیاتی خودشان را بشناسند. همان‌طور که اگر جاده بد باشد، باز هم راننده باید برای سلامت خودش محتاط رانندگی کند، اگر اجرای مالیاتی هم ایراد دارد، ناآگاهی فرد از قانون معمولاً از مسئولیت او کم نمی‌کند.','هر دو اقدام احتیاط و شناخت تکلیف در قیاس صریح است؛ پاسخ نتیجه حقوقی قطعی دیگری نمی‌افزاید.')]],dimensions={
      'evidence_sufficiency':'هر دو بخش سؤال در صفر مستقیم‌اند.',
      'question_answer_fit':'اقدام راننده و اقدام در اجرای معیوب مالیاتی هر دو پاسخ داده شدند.',
      'factual_claim_support':'claim واحد هر دو اقدام پاسخ را پوشش دارد.',
      'scope_modality_negation_quantity':'مضمون قیاس متن است؛ تقصیر ساختار به فرد نسبت داده نشده و معمولاً به حکم مطلق حقوقی تبدیل نشده.',
      'outside_details':'قانون جاری، نرخ، جریمه یا دستور مالیاتی شخصی بیرونی ندارد.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'اثر عوامل بیرونی در دوم و سوم پذیرفته شده؛ با احتیاط و شناخت تکلیف تعارض ندارد. شواهد بیمه پاسخ بخش مالیاتی نیستند.'})
    b=decision(340,'تمام ده شاهد خوانده شد. صفر درباره افرادی است که ریشه مشکل را نمی‌دانند یا رفع آن را فراتر از توان خود می‌بینند و سپس به رمال و فالگیر متوسل می‌شوند. پاسخ همین وصف گروه متن را می‌دهد؛ افراد تمام جوامع، همه مشکلات و همه احساس ناتوانی را به حکم قطعی رفتاری تعمیم نمی‌دهد. اول انتخاب میان توانمندی و پناه‌بردن را شرح می‌دهد؛ داستان‌های دیگر نمونه حل مسئله و ناتوانی‌اند و تعریف گروه را نقض نمی‌کنند.',[[(0,'این افراد دربارۀ ریشۀ مشکلشان چیزی نمی‌دانند، دانشی ندارند یا رفع آن مشکل را ورای توانایی خود می‌بینند؛ بنابراین دست به دامان رمالان و فالگیران می‌شوند.','دو وصف ناآگاهی از ریشه یا ادراک ناتوانی و مراجعه به دو گروه مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر گروه مورد سؤال و دو وصف را مستقیم نام می‌برد.',
      'question_answer_fit':'چه کسانی به رمال و فالگیر پناه می‌برند در چارچوب متن پاسخ داده شد.',
      'factual_claim_support':'claim واحد تمام وصف گروه پاسخ را پوشش دارد.',
      'scope_modality_negation_quantity':'یا و ادراک فرد از توان حفظ‌اند؛ ناتوانی عینی همه افراد یا حکم رفتاری همگانی ادعا نشده.',
      'outside_details':'تشخیص بالینی، آمار رمالی یا علل بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'اول توانمندسازی را بدیل مراجعه معرفی می‌کند؛ شواهد داستانی دیگر تعارضی با وصف گروه متن ندارند.'})
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==820
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0012';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[339,340],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0012/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=26,total_reviewed=822,remaining=327,next_position=341)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_339_340_v1',[339,340],'دو KEEP339 و340؛ ادامه341.',cp['created_utc'])
