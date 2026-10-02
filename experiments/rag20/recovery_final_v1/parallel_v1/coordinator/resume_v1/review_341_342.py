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
    ins=rows(ROOT/'inputs.jsonl');outs=rows(ROOT/'outputs.jsonl')
    ev=json.loads(ins[340]['messages'][1]['content'])['evidence'];r=copy.deepcopy(outs[340]['response'])
    r['answer_text']='در این متن، شغل دوم لزوماً کاری نامرتبط نیست؛ می‌تواند فعالیتی کنار شغل اصلی با سبک دیگری در همان تخصص باشد، مثل مشاورهٔ مدیر منابع انسانی به سازمانی دیگر.'
    r['claims']=[dict(claim_text=r['answer_text'],claim_type='FACTUAL',evidence_ids=[ev[3]['evidence_id']])]
    a=decision(341,'تمام ده شاهد خوانده شد. تعریف جامع اصطلاحی نیست، اما شاهد سوم توضیح مستقیم و مثال شغل دوم در کنار شغل اصلی با سبک دیگر را دارد؛ امتناع کامل این پاسخ محدود و مفید را حذف می‌کرد. پاسخ با قید در این متن و می‌تواند اصلاح شد و claim با سوم دوباره بررسی شد. پنجم و ششم هم‌راستایی تخصص را پیشنهاد می‌کنند؛ این پیشنهاد به تعریف اجباری همه شغل‌های دوم تبدیل نشده است.',[[(3,'مثلاً من توی یه سازمانی مدیر منابع انسانی‌ام، اونجا موفقیت‌های بزرگی تو اون حوزه پیدا کردم، یه\nسازمان بزرگی دیگه می‌گه هفته‌ای دو، سه ساعت می‌تونی به ما مشاوره بدی؟ یعنی در\nکنارش این یه معنا ما رو می‌بره مثلاً، مثلاً شغل دوم. یعنی شغل دوم لزوماً یه کار دیگه‌ای نیست،\nبلکه یه سبک دیگه‌ست.','فعالیت مشاوره در کنار مدیریت اصلی و تفاوت سبک به‌عنوان توضیح شغل دوم در متن مستقیم آمده‌اند.')]],repair=r,dimensions={
      'evidence_sufficiency':'برای شرح محدود شغل دوم و مثال، سوم مستقیم کافی است؛ تعریف جامع حقوقی نیست.',
      'question_answer_fit':'توضیح خود متن با قید دامنه ارائه شد و امتناع کامل رفع شد.',
      'factual_claim_support':'claim واحد همه تعریف محدود و مثال پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'لزوماً و می‌تواند حفظ‌اند؛ همه شغل‌های دوم همان تخصص اعلام نشده‌اند.',
      'outside_details':'ساعات قانونی، قرارداد، طبقه‌بندی رسمی یا تعریف بیرونی افزوده نشده.',
      'abstention_justified':'ORIGINAL_OVERBROAD_REPAIRED',
      'ambiguity_conflict':'شواهد پنجم و ششم تخصص مشترک را پیشنهاد می‌کنند؛ وجود شغل‌های دوم نامرتبط در پنجم با لزوماً نامرتبط نیست سازگار است.'})
    a['audit']['error_categories']=['overbroad abstention']
    a['repair']['reason_fa']='نبود تعریف جامع موجب حذف شرح مستقیم و مثال موجود شده بود؛ پاسخ محدود به متن جایگزین شد.'
    a['repair']['recheck_reason_fa']='قید متن، امکان سبک متفاوت، کنار شغل اصلی و مثال منابع انسانی با سوم دوباره تطبیق شدند.'
    ev=json.loads(ins[341]['messages'][1]['content'])['evidence'];r=copy.deepcopy(outs[341]['response'])
    r['answer_text']='از منابع اطلاعاتی مطرح‌شده، مشتریان و پیشنهادها و شکایت‌هایشان، دوستان و آشنایان و بازخوردشان دربارهٔ محصول، اتحادیه‌ها، انجمن‌ها، سازمان‌های مرتبط و فعالان بازار، و اخبار و اطلاعات‌اند.'
    r['claims']=[dict(claim_text='مشتریان و حرف‌ها، پیشنهادها و شکایت‌هایشان منبع اطلاعات‌اند.',claim_type='FACTUAL',evidence_ids=[ev[4]['evidence_id']]),dict(claim_text='دوستان و آشنایان و بازخوردشان درباره محصول برای کسب‌وکارهای کوچک منبع اطلاعات‌اند.',claim_type='FACTUAL',evidence_ids=[ev[0]['evidence_id']]),dict(claim_text='اتحادیه‌ها، انجمن‌ها، سازمان‌های مرتبط، فعالان بازار و اخبار و اطلاعات از منابع مطرح‌شده‌اند.',claim_type='FACTUAL',evidence_ids=[ev[4]['evidence_id']])]
    b=decision(342,'تمام ده شاهد خوانده شد. پاسخ اصلی فقط دوستان و آشنایان را می‌گفت و اصلی‌ترین منبع یعنی مشتری و منابع صریح دیگر چهارم را حذف می‌کرد. پاسخ با فهرست منابع مطرح‌شده تکمیل و سه claim مستقل با صفر و چهارم دوباره بررسی شد. سوم، ششم و هفتم نقش مشتری و نقد را تأیید می‌کنند؛ اول داده زمان مراجعه را نمونه اطلاعات مشتری می‌گوید. منابع مالی و انسانی و برند در دوم و نهم با منابع اطلاعاتی خلط نشده‌اند؛ فهرست همه منابع جهان ادعا نشده است.',[
      [(4,'یکی از اصلی‌ترین منابع، مشتریه: حرف‌هاش، پیشنهادهاش، شکایت‌هاش.','مشتری و هر سه نوع بیان او مستقیم نام برده شده‌اند.')],
      [(0,'برای کسب‌وکارهای کوچک حتی دوستان و آشنایان هم منبع اطلاعاتن.','دوستان و آشنایان در کسب‌وکار کوچک منبع‌اند.'),(0,'می‌تونه چند نفر رو دعوت کنه، محصول رو در اختیارشون بذاره و واقعاً بپرسه: بو، طعم، شکل، کیفیت، بسته‌بندی، کاربرد و قیمت رو چطور دیدین؟','بازخورد درباره محصول، کاربرد منبع دوستان و آشنایان است.')],
      [(4,'می‌تونیم با اتحادیه‌ها، انجمن‌ها، سازمان‌های مرتبط و فعالان بازار هم ارتباط بگیریم.','چهار گروه ارتباطی مستقیم آمده‌اند.'),(4,'اخبار و اطلاعات هم منبع مهمیه.','اخبار و اطلاعات صریحاً منبع خوانده شده‌اند.')]],repair=r,dimensions={
      'evidence_sufficiency':'صفر و چهارم منابع نام‌برده را مستقیم دارند و شواهد دیگر نقش مشتری را تأیید می‌کنند.',
      'question_answer_fit':'فهرست از نمونه دوستان به منابع اصلی مطرح‌شده تکمیل شد.',
      'factual_claim_support':'سه claim همه اقلام پاسخ فعال را پوشش می‌دهند.',
      'scope_modality_negation_quantity':'از منابع مطرح‌شده است؛ فهرست بسته و جامع جهانی یا انحصار دوستان نیست.',
      'outside_details':'منبع فرضی و ادعای صحت همیشگی بازخورد اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'منابع کلیدی پول و نیروی انسانی و برند با منابع اطلاعاتی فرق دارند؛ گزارش‌های بورسی پنجم زمینه خاص جدا هستند و پاسخ به منابع متن طراحی کسب‌وکار محدود است.'})
    b['audit']['error_categories']=['incomplete question coverage']
    b['repair']['reason_fa']='مشتریان و منابع صریح ارتباطی و خبری حذف شده بودند؛ فهرست و claims تکمیل شدند.'
    b['repair']['recheck_reason_fa']='همه اقلام پاسخ با صفر و چهارم دوباره تطبیق شدند؛ هر گروه claim و span خود را دارد.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==822
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0013';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[341,342],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0013/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=28,total_reviewed=824,remaining=325,next_position=343)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_341_342_v1',[341,342],'دو اصلاح341 و342؛ ادامه343.',cp['created_utc'])
