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
    outs=rows(ROOT/'outputs.jsonl')
    r=copy.deepcopy(outs[329]['response'])
    r['answer_text']='چیدن پشم، بافتن پارچه و دوختن شنل.'
    r['claims'][0]['claim_text']=r['answer_text']
    a=decision(330,'تمام ده شاهد خوانده شد. شاهد صفر مراحل همراهی کودک با چوپان را چیدن پشم، بافتن پارچه و دوختن آن می‌گوید. پاسخ اولیه پایان فرایند را تهیه شنل می‌نامید و مرحله صریح دوختن را نمی‌گفت؛ همان مرحله جایگزین عبارت مبهم شد. پاسخ فعال و claim با جمله کامل شاهد دوباره تطبیق شدند. سایر کتاب‌های خرید، پس‌انداز و هدیه مراحل این کتاب را تغییر نمی‌دهند؛ شاهد ششم فقط موضوع کلی تولید را تأیید می‌کند.',[[(0,'بچه‌ها با چوپان همراه می‌شوند و مراحل تهیه یک شنل را از چیدن پشم گرفته تا بافتن پارچه و دوختن آن، دنبال می‌کنند.','سه مرحله و ترتیب آنها برای همین کتاب مستقیم آمده است.')]],repair=r,dimensions={
      'evidence_sufficiency':'شاهد صفر سه مرحله را صریح می‌گوید.',
      'question_answer_fit':'هر سه مرحله نام برده شد؛ مرحله دوختن دیگر مبهم نیست.',
      'factual_claim_support':'claim واحد هر سه جزء پاسخ فعال را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'مراحل نقل‌شده همین کتاب و ترتیب آنها حفظ شده است.',
      'outside_details':'ریسندگی، رنگرزی یا مراحل فرضی دیگر اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'کتاب‌های دیگر شاهد مراحل این کتاب نیستند؛ تعارض مرتبط دیده نشد.'})
    a['audit']['error_categories']=['incomplete question coverage']
    a['repair']['reason_fa']='عبارت مبهم تهیه شنل با مرحله صریح دوختن شنل جایگزین شد.'
    a['repair']['recheck_reason_fa']='هر سه مرحله پاسخ و claim فعال با جمله کامل شاهد صفر دوباره تطبیق شدند.'
    r=copy.deepcopy(outs[330]['response'])
    r['claims'][0]['evidence_ids']=[json.loads(rows(ROOT/'inputs.jsonl')[330]['messages'][1]['content'])['evidence'][3]['evidence_id']]
    r['answer_text']='در الگوی هدف پس‌اندازی کودکان، بیست درصد پول‌توجیبی برای آینده پیشنهاد شده است.'
    r['claims'][0]['claim_text']=r['answer_text']
    b=decision(331,'تمام ده شاهد خوانده شد. شواهد صفر، اول و سوم پیشنهاد بیست درصد پول‌توجیبی برای اهداف پس‌اندازی کودکان را دارند. شاهد پنجم برای نوجوانان الگوی متفاوت خرج، پس‌انداز و سرمایه‌گذاری دارد؛ بنابراین پاسخ به الگوی هدف پس‌اندازی کودکان مقید شد تا بیست درصد حکم تمام سنین تلقی نشود. پاسخ و claim فعال دوباره با شاهد سوم بررسی شدند. هشتاد درصد هدیه، پنج درصد درآمد بزرگسال و درصدهای پیمایش جمعیت‌های دیگر با این مقدار خلط نشده‌اند.',[[(3,'در این باره می‌توان دو نوع هدف پس‌اندازی در نظر گرفت، کوتاه مدت و بلندمدت. کودکان برای هردو از پول توجیبی بخشی را کنار می‌گذارند. پیشنهاد می‌شود برای هر دوی آن، بیست درصد کنار بگذارند و هشتاد درصد را خرج کنند.','هم کودکان، هم نوع الگوی اهداف و هم پیشنهاد بیست درصد صریح است؛ نه قانون همه سنین.')]],repair=r,dimensions={
      'evidence_sufficiency':'سه شاهد الگوی بیست درصد را برای اهداف پس‌اندازی کودکان تصریح می‌کنند.',
      'question_answer_fit':'درصد مورد سؤال با تعیین الگوی مربوط پاسخ داده شد.',
      'factual_claim_support':'claim واحد مقدار، مخرج پول‌توجیبی و محدوده الگو را پوشش دارد.',
      'scope_modality_negation_quantity':'بیست درصد پیشنهاد همین الگو است؛ نه الزام یا الگوی تمام سنین و تمام دریافتی‌ها.',
      'outside_details':'توصیه مالی بیرونی و تضمین رسیدن به هدف اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'الگوی نوجوانان در پنجم متفاوت است؛ دامنه پاسخ به الگوی هدف پس‌اندازی کودکان محدود شد. هدیه و درآمد بزرگسال مخرج متفاوت دارند.'})
    b['audit']['error_categories']=['scope ambiguity']
    b['repair']['reason_fa']='با وجود الگوهای سنی متفاوت، محدوده بیست درصد در پاسخ و claim به الگوی هدف پس‌اندازی کودکان تصریح شد.'
    b['repair']['recheck_reason_fa']='مقدار، مخرج، پیشنهاد بودن و دامنه الگو دوباره با شاهد سوم بررسی شد؛ الگوی نوجوانان و درصد هدیه جدا ثبت شدند.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==811
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0008';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[330,331],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0008/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=17,total_reviewed=813,remaining=336,next_position=332)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_330_331_v1',[330,331],'دو اصلاح و بازبینی330 و331؛ ادامه332.',cp['created_utc'])
