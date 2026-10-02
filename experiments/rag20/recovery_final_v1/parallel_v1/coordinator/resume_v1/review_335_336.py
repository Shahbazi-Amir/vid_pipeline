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
    a=decision(335,'تمام ده شاهد خوانده شد. معرفی‌های قسمت‌های مختلف چهلستون قالب گفتگومحور و موضوع ریشه‌های رفتار مالی و ضرورت سواد مالی را تکرار می‌کنند. شاهد ششم نیز تصریح می‌کند گفت‌وگو درباره مبانی است، نه دوره مستقیم آموزش. پاسخ همین قالب و موضوع را می‌گوید و آن را کلاس کاربردی مستقیم یا پخش فعلی با زمان قطعی معرفی نمی‌کند.',[[(0,'در 40 برنامه گفتگومحور با عنوان «چهلستون» از رادیو گفتگو پخش می‌شود. این گفتگوها به بررسی ریشه‌های فرهنگی، اجتماعی رفتارهای مالی ایرانیان و ضرورت‌های سواد مالی در گروه‌های هدف مختلف سواد مالی می‌پردازد.','قالب گفتگومحور و هر دو موضوع رفتار مالی و سواد مالی صریح است.')]],dimensions={
      'evidence_sufficiency':'معرفی قسمت‌ها و شرح ششم قالب و موضوع را روشن می‌کنند.',
      'question_answer_fit':'نوع برنامه و موضوع آن پاسخ داده شد.',
      'factual_claim_support':'claim واحد قالب و هر دو موضوع پاسخ را پوشش دارد.',
      'scope_modality_negation_quantity':'دوره مستقیم آموزش یا برنامه پخش فعلی ادعا نشده.',
      'outside_details':'زمان پخش امروز یا دسترسی فعلی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'ششم مبانی و گفتگو را از آموزش مستقیم جدا می‌کند و با پاسخ سازگار است.'})
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[335]['response'])
    r['answer_text']='در تحقیقات بازار، کسب‌وکارهای بزرگ به مؤسسات پول می‌دهند؛ کوچک‌ها می‌توانند در مقیاس خود بازخورد محصول را جمع کنند، به شرط اینکه فقط افراد همواره تأییدکننده را انتخاب نکنند.'
    r['claims'][0]['claim_text']=r['answer_text']
    b=decision(336,'تمام ده شاهد خوانده شد. صفر درباره تحقیقات بازار بزرگ‌ها و جمع‌آوری بازخورد در مقیاس کوچک است و شرط انتخاب نکردن صرفاً تأییدکنندگان را دارد. پاسخ اولیه این شرط را حذف کرده بود. شرط در پاسخ و claim فعال درج و با کل جمله شاهد دوباره بررسی شد. چون پنجم درباره مقایسه خرید تأمین‌کننده نیز هست، موضوع تحقیقات بازار صریح شد؛ حکم پاسخ به تمام رفتارهای شرکت‌های بزرگ تعمیم ندارد. اول مزیت بازخورد سریع کوچک‌ها را تأیید می‌کند.',[[(0,'کسب‌وکارهای بزرگ برای همین کار به مؤسسات تحقیقات بازار پول می‌دن. کسب‌وکار کوچک هم می‌تونه در مقیاس خودش همین کار رو بکنه؛ به شرط این‌که فقط آدم‌هایی رو انتخاب نکنه که همیشه تأییدش می‌کنن.','مقایسه بزرگ و کوچک، مقیاس و شرط نقدپذیری نمونه جمع‌آوری بازخورد در یک جمله است.'),
      (0,'می‌تونه چند نفر رو دعوت کنه، محصول رو در اختیارشون بذاره و واقعاً بپرسه: بو، طعم، شکل، کیفیت، بسته‌بندی، کاربرد و قیمت رو چطور دیدین؟','همین کار به پرسیدن بازخورد ویژگی‌های محصول در جمله قبل اشاره می‌کند.')]],repair=r,dimensions={
      'evidence_sufficiency':'صفر هم رفتار دو مقیاس و هم شرط انتخاب نمونه را تصریح کرده است.',
      'question_answer_fit':'مقایسه دو گروه در زمینه تحقیقات بازار پاسخ داده شد.',
      'factual_claim_support':'claim فعال کل مقایسه، موضوع و شرط پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'شرط انتخاب نکردن فقط تأییدکنندگان حفظ شد؛ موضوع به تحقیقات بازار محدود است.',
      'outside_details':'هزینه پژوهش، اندازه نمونه آماری یا تضمین فروش اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'پنجم مقایسه تأمین‌کننده است؛ پاسخ زمینه تحقیقات بازار را مشخص کرده تا دو مقایسه خلط نشوند.'})
    b['audit']['error_categories']=['omitted condition','scope ambiguity']
    b['repair']['reason_fa']='شرط نمونه صرفاً تأییدکننده حذف شده بود؛ افزوده و زمینه تحقیقات بازار تصریح شد.'
    b['repair']['recheck_reason_fa']='متن پاسخ و claim فعال با جمله مقایسه و مثال بازخورد صفر بررسی شدند؛ شرط و زمینه حفظ‌اند.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==816
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0010';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[335,336],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0010/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=22,total_reviewed=818,remaining=331,next_position=337)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_335_336_v1',[335,336],'KEEP335 و اصلاح شرط336؛ ادامه337.',cp['created_utc'])
