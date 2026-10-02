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
    a=decision(351,'تمام ده شاهد با متن کامل بررسی شد؛ متن‌های عیناً مشترک با344 نیز قبلاً کامل خوانده شده بودند. صفر مدل نیاز سپس مصرف را مطرح و سپس همیشه این‌طور عمل نمی‌کند را با هویت، کاهش تنش، نمایش جایگاه و تبلیغ توضیح می‌دهد. پاسخ نفی همیشه و امکان اثر چهار عامل را حفظ می‌کند. سایر شواهد اقتصاد رفتاری، آگاهی پایه و وضعیت بدنی این تک‌عاملی نبودن را تأیید می‌کنند؛ مثال سود ساده و مرکب تعریف رفتار همگانی نیست.',[[(0,'مدل ساده اقتصادی می‌گوید نیاز داریم، پس مصرف می‌کنیم؛ مثل خودرو که برای حرکت به سوخت نیاز دارد. اما انسان همیشه این‌طور عمل نمی‌کند.\nگاهی برای اثبات هویت، کاهش تنش عاطفی، نمایش جایگاه یا تحت تأثیر تبلیغ خرید می‌کنیم.','نفی همیشه و چهار عامل غیرنیاز مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر هر دو بخش پاسخ و چهار عامل را صریح دارد.',
      'question_answer_fit':'پرسش همیشه با خیر و عوامل توضیح‌دهنده پاسخ داده شد.',
      'factual_claim_support':'claim واحد نفی همیشگی و همه چهار عامل را پوشش دارد.',
      'scope_modality_negation_quantity':'می‌تواند و نفی همیشه حفظ‌اند؛ نفی همه رفتار عقلانی نیست.',
      'outside_details':'آمار رفتار یا مدل اقتصادی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'مدل ساده نیاز و مصرف در صفر معلوم است؛ عوامل دیگر در سایر شواهد مکمل‌اند.'})
    reason='تمام ده شاهد با متن کامل بررسی شد؛ چهار شاهد مشترک اهداف کودک نیز قبلاً کامل خوانده شده بودند. سؤال نوع پس‌انداز قابل قبول را بدون معیار، سن، افق یا روش مشخص می‌پرسد. صفر و دوم سه افق و هدف، اول نقد صندوق خانوادگی دیرنوبت در تورم، پنجم ویژگی هدف کودک، هفتم سن و فاصله زمانی و هشتم رنج خوشایند را دارند. هیچ زمینه یکتا برای انتخاب یک نوع به‌عنوان قابل قبول در سؤال نیست. پاسخ فقط نامشخص بودن موردنظر را می‌گوید؛ وجود پیشنهادهای متنوع در شواهد را نفی نمی‌کند.'
    answer=rows(ROOT/'outputs.jsonl')[351]['response']['answer_text']
    b=decision(352,reason,[],dimensions={
      'evidence_sufficiency':'انواع و معیارهای متفاوت موجودند؛ معیار موردنظر سؤال معلوم نیست.',
      'question_answer_fit':'امتناع محدود متناسب با ابهام قابل قبول و فقدان زمینه است.',
      'factual_claim_support':'کل پاسخ محدودیت زمینه است و ادعای مالی تازه ندارد؛ claims خالی درست است.',
      'scope_modality_negation_quantity':'فقط نوع موردنظر همین سؤال نامعلوم است؛ عدم وجود پس‌انداز مطلوب در جهان ادعا نشده.',
      'outside_details':'نوع، سن، نرخ تورم یا هدف کاربر حدس زده نشده.',
      'abstention_justified':'JUSTIFIED',
      'ambiguity_conflict':'پذیرش از منظر تورم، سن کودک، افق و رنج خوشایند معیارهای متفاوت است و سؤال یکی را انتخاب نکرده.'},units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)])
    b['audit']['status']='VALID_ABSTENTION';b['support']['abstention_review']='JUSTIFIED'
    c=decision(353,'تمام ده شاهد با متن کامل بررسی شد؛ شاهد زمان مراجعه مشتری مشترک با342 قبلاً کامل خوانده شده بود. صفر شناخت مشتری درست و انجام ندادن الزاماً هر درخواست را با ظرفیت تولید شرح می‌دهد. اول طراحی مدل بر مدار مشتری را مطرح می‌کند؛ این مکمل شناخت مشتری مناسب است، نه الزام تغییر خط تولید برای هر درخواست. پاسخ هر دو شناخت و تناسب با ظرفیت و نفی هر درخواست را دارد؛ مشتری‌مداری را بی‌اعتنایی به مشتری نمی‌نامد.',[[(0,'اگر تولید انبوه داریم و یک نفر زنگ می‌زنه و یک سفارش کاملاً خاص می‌خواد، لازم نیست به‌خاطر «مشتری‌مداری» کل خط تولید رو به هم بزنیم.\nبستگی به تیراژ و ظرفیت داره.','تناسب با مدل و ظرفیت به جای تغییر برای هر درخواست صریح است.'),(0,'مشتری‌مداری یعنی **مشتری درست خودمون رو بشناسیم**، نه این‌که هرکس هر چیزی خواست ما هم حتماً انجام بدیم.','شناخت مشتری مناسب و نفی اجرای الزامی همه درخواست‌ها مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر تعریف و محدودیت ظرفیت را مستقیم دارد.',
      'question_answer_fit':'معنای مشتری‌مداری در مدل کسب‌وکار پاسخ داده شد.',
      'factual_claim_support':'claim واحد شناخت و خدمت متناسب و نفی هر درخواست را پوشش دارد.',
      'scope_modality_negation_quantity':'انجام هر درخواست لازم نیست؛ رد همه درخواست‌های خاص یا بی‌توجهی به مشتری نیست.',
      'outside_details':'قانون حقوق مشتری یا تعهد قراردادی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'اول طراحی مدل بر مدار مشتری و صفر انتخاب مشتری درست و ظرفیت را می‌گویند؛ این دو الزام پاسخ به همه افراد و درخواست‌ها ایجاد نمی‌کنند.'})
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[353]['response'])
    r['answer_text']='اگر منظور رفتار برخلاف قواعد عقلانیت است، متن آن را به رفتار بر مبنای ادراک فرد از واقعیت توضیح می‌دهد؛ «این‌جور» در سؤال دقیق‌تر مشخص نشده است.'
    r['claims'][0]['claim_text']='در توضیح متن درباره رفتار برخلاف قواعد عقلانیت، فرد بر مبنای ادراک خود از واقعیت رفتار می‌کند.'
    reason='تمام ده شاهد با متن کامل بررسی شد؛ شواهد مشترک باورها قبلاً در350 کامل خوانده شده بودند. صفر رابطه رفتار خلاف قواعد عقلانیت و ادراک را دارد اما این‌جور در سؤال مرجع ندارد و شواهد از خرید کودکانه، بدهی، ارزش‌گذاری فقر و گریز از آزادی هم می‌گویند. پاسخ قطعی اولیه به پاسخ شرطی درباره عقلانیت محدود و ابهام باقی‌مانده صریح شد. قسمت واقعی و claim با صفر و جمله محدودیت با همه زمینه‌ها دوباره بررسی شدند.'
    d=decision(354,reason,[[(0,'وقتی که حول خطاهای ادراکی می‌زنیم، یعنی لزوماً ما آدم‌ها مبتنی بر این قواعد و شاخص‌های عقلانیت رفتار نمی‌کنیم.','موضوع رفتار خلاف شاخص عقلانیت در این بحث است.'),(0,'ما بر اساس ادراک خود از واقعیت\nرفتار می‌کنیم.','پایه ادراک واقعیت در شرح گوینده مستقیم است.')]],repair=r,dimensions={
      'evidence_sufficiency':'برای شرح شرطی عقلانیت کافی است؛ برای تعیین قطعی مرجع این‌جور کافی نیست.',
      'question_answer_fit':'پاسخ شرطی داده و مرجع حل‌نشده را آشکار کرده است.',
      'factual_claim_support':'claim بخش واقعی پاسخ را دارد؛ جمله آخر محدودیت زمینه است.',
      'scope_modality_negation_quantity':'اگر منظور و متن حفظ‌اند؛ علت یکتای رفتار نامعلوم ادعا نشده.',
      'outside_details':'تشخیص روانی یا علت حدسی رفتار اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'موضوعات خرید، بدهی، فقر و آزادی مرجع یکتا نمی‌دهند؛ شرط عقلانیت در پاسخ فعال این ابهام را پنهان نمی‌کند.'},units=[dict(text=r['answer_text'].split('؛')[0]+'؛',kind='FACTUAL',claim_indices=[0],reason_fa='شرح شرطی ادراک با صفر پوشش دارد.'),dict(text=r['answer_text'].split('؛')[1],kind='EVIDENCE_LIMITATION',claim_indices=[],reason_fa='این‌جور در سؤال مرجع مشخص ندارد؛ زمینه‌های متعدد خوانده شدند.')])
    d['audit']['error_categories']=['unresolved question reference']
    d['repair']['reason_fa']='مرجع این‌جور نامشخص بود؛ پاسخ به شرح شرطی عقلانیت محدود و ابهام آشکار شد.'
    d['repair']['recheck_reason_fa']='قسمت واقعی و claim با صفر و محدودیت مرجع با همه ده شاهد دوباره بررسی شدند.'
    e=decision(355,'تمام ده شاهد با متن کامل بررسی شد. صفر و شواهد اول، دوم، چهارم، پنجم، ششم و هشتم سقف درآمد ناشی از فعالیت و عدم افزایش لزوماً با کار بیشتر را می‌گویند. پاسخ نه همیشه را حفظ می‌کند و نمی‌گوید افزایش کار هیچ وقت درآمد را بالا نمی‌برد. سوم امکان تغییر سبک و نهم دشواری افزایش درآمد را دارند؛ ظرفیت سبک فعلی با نفی همه راه‌های رشد درآمد خلط نشده است.',[[(0,'میزان درآمدزایی ناشی از فعالیت به سقف خود می‌رسد و از جایی به بعد، هر قدر بیشتر فعالیت کنیم، تأثیری در افزایش درآمد ندارد.','وجود سقف و بی‌اثر شدن تلاش بیشتر پس از آن هر دو مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر و چند شاهد دیگر سقف و شرط پس از رسیدن به آن را مستقیم دارند.',
      'question_answer_fit':'پرسش افزایش فعالیت با نه همیشه و توضیح سقف پاسخ داده شد.',
      'factual_claim_support':'claim واحد نفی همیشه، سقف و عدم افزایش لزوماً را پوشش دارد.',
      'scope_modality_negation_quantity':'نه همیشه و لزوماً حفظ‌اند؛ عدم امکان رشد درآمد در همه سبک‌ها و شرایط ادعا نشده.',
      'outside_details':'حد ساعات قطعی، رقم حقوق یا بازده سرمایه‌گذاری اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'تغییر سبک یا مهارت در سوم و نهم می‌تواند درآمد تازه دهد؛ پاسخ فقط محدودیت افزایش فعالیت همان شغل را گزارش می‌کند.'})
    return [a,b,c,d,e]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==832
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0017';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[351,352,353,354,355],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0017/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=41,total_reviewed=837,remaining=312,next_position=356)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_351_355_v1',[351,352,353,354,355],'سه KEEP و یک امتناع موجه و یک رفع ابهام351–355؛ ادامه356.',cp['created_utc'])
