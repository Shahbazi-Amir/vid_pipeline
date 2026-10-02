import sys,json,copy
from pathlib import Path
from datetime import datetime,timezone
r=Path('vid_pipeline/experiments/rag20/recovery_final_v1');sys.path.insert(0,str(r))
import incremental_review as f
from decisions_006_010 import decision
from audit_structure import save
from review_recheck_notes import NOTES
c,s=f.verify_current();i,o=f.source_rows();active,revs=f.active(f.index(o),s['repairs.jsonl']);aud=f.index(s['audit.jsonl']);sup=f.index(s['support.jsonl'])
w=r/'parallel_v1/coordinator/resume_v1/rechecks_v1';w.mkdir(exist_ok=True)
ds=[]
def revise(pos,answer,items,status='REVIEW_REQUIRED',lim='',reason=None):
 p=json.loads(i[pos-1]['messages'][1]['content']);ev=p['evidence'];cid=i[pos-1]['candidate_id']
 claims=[dict(claim_text=t,claim_type='FACTUAL',evidence_ids=[ev[n]['evidence_id']]) for t,n,q in items]
 response=dict(answer_text=answer+lim,claims=claims)
 units=([dict(text=answer,kind='FACTUAL',claim_indices=list(range(len(claims))),reason_fa='بند واقعی با شواهد نقل‌شده پوشش دارد.')] if claims else [])
 if lim:units.append(dict(text=lim,kind='EVIDENCE_LIMITATION',claim_indices=[],reason_fa='محدودیت پس از بازخوانی ده شاهد ثبت شد.'))
 if not units:units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa='مرجع سؤال مشخص نیست.')]
 reason=reason or NOTES[pos][1]
 d=decision(pos,reason,[[(n,q,'نقل دقیق متن از دامنه همین مثال حمایت می‌کند.')] for t,n,q in items],repair=response,units=units)
 rev=aud[cid].get('revision',0)+1
 for name in ['audit','support','repair']:d[name]['revision']=rev
 d['repair'].update(previous_response_sha256=active[cid]['response_sha256'],reason_fa=reason)
 d['audit']['status']=status
 if status=='REVIEW_REQUIRED':d['audit']['dimensions'].update(evidence_sufficiency='PARTIAL_OR_UNRESOLVED',question_answer_fit='QUESTION_CONTEXT_UNRESOLVED',ambiguity_conflict='REQUIRES_SOURCE_OR_QUESTION_CLARIFICATION')
 ds.append(d)
for pos in [1,3,4,5]:
 cid=i[pos-1]['candidate_id'];p=json.loads(i[pos-1]['messages'][1]['content']);ev=p['evidence']
 specs=[[(next(n for n,e in enumerate(ev) if e['evidence_id']==sp['evidence_id']),sp['quote'],cr['reason_fa']) for sp in cr['supporting_spans']] for cr in sup[cid]['claim_results']]
 reason=aud[cid]['reason_fa']+' بازخوانی کامل ده شاهد و بررسی پوشش تمام بندهای پاسخ در بازبینی نهایی انجام شد.'
 d=decision(pos,reason,specs,repair=copy.deepcopy(active[cid]['response']))
 d['audit']['status']='KEEP';d['repair']['reason_fa']='متن پاسخ حفظ شد؛ قرارداد پوشش کامل بندهای پاسخ به نسخه دو ارتقا یافت.'
 ds.append(d)
revise(2,'در اندرز نقل‌شده، خردمند تلاش و کوشش را فراموش نمی‌کند و با ثبات قدم و پشتکار از تنبلی می‌گریزد.',[('در اندرز نقل‌شده، خردمند تلاش و کوشش را فراموش نمی‌کند و با ثبات قدم و پشتکار از تنبلی می‌گریزد.',2,'فراموشی تلاش و کوشش، دور از خرد است؛ چون اسباب خوشبختی و بهره‌مندی، بیشتر نصیب کسی می‌شود که اهل تلاش و کوشش باشد و با ثبات قدم و پشتکار از تنبلی بگریزد.')],status='REPAIRED')
revise(481,'در بیت نقل‌شده درباره «آن مرد»، دخل نوزده و خرج بیست است؛',[('در بیت نقل‌شده درباره «آن مرد»، دخل نوزده و خرج بیست است.',0,'بر احوال آن مرد باید گریست که دخلش بود نوزده، خرج بیست.')],status='REPAIRED',lim=' واحد پولی در بیت مشخص نشده است.')
revise(613,'در یک مثال سی‌ساله، حدود ده میلیارد تومان و در مثال دیگری با نگهداری اصل و سود، حدود هفده میلیارد تومان ذکر شده است؛',[('در یک مثال سی‌ساله حدود ده میلیارد تومان ذکر شده است.',1,'اگر من 30 سال سرمایه‌گذاری بکنم\nمی‌شه 10 میلیارد حدودا'),('در مثال نگهداری اصل و سود، حدود هفده میلیارد تومان در انتهای سال سی ذکر شده است.',3,'بهترینش اینه که من به اصل و سود پول دست نزنم که می‌شه ۱۷ میلیارد، و در حالت پس‌انداز ۳۶ میلیون. شما ۳۶ میلیون رو مقایسه بکنید با ۱۷ میلیارد تومان در انتهای سال ۳۰.')],lim=' سؤال مبلغ واریز، نرخ بازده و شیوه سرمایه‌گذاری را تعیین نکرده، بنابراین یک مبلغ واحد قابل انتخاب نیست.')
revise(641,'منظور از «رویکرد اول» مشخص نیست؛ از این شواهد نمی‌توان محور واحدی را برای سؤال تعیین کرد.',[])
revise(776,'در مدل برداشت اصل و سود هر سال، شاهد رقم ۴۶ میلیون و ۸۰۰ هزار تومان را برای پایان سی سال می‌گوید؛ در مدل دیگری با سود ساده، رقم ۱۹۲ میلیون و ۶۰۰ هزار تومان آمده است؛',[('در مدل برداشت اصل و سود هر سال، شاهد رقم ۴۶ میلیون و ۸۰۰ هزار تومان را برای پایان سی سال می‌گوید.',0,'در انتهای سال سی‌ام چهل‌وشش میلیون و هشتصد هزار تومان داره.'),('در مدل دیگری با سود ساده، رقم ۱۹۲ میلیون و ۶۰۰ هزار تومان برای دوره سی‌ساله آمده است.',9,'توی این سی سال اگر مای سد تومن بذارم کنار\nو سود سادم بگیرم\nمی‌شه 192 میلیون و 600 هزار تومن دارایی من')],lim=' سؤال مشخص نمی‌کند کدام مدل موردنظر است.')
revise(778,'در شواهد بررسی‌شده آموزش مبتنی بر استاندارد جامپ‌استارت مطرح است؛',[('در شواهد بررسی‌شده آموزش مبتنی بر استاندارد جامپ‌استارت مطرح است.',0,'این مبتنی بر استاندارد جامپ‌استارت')],lim=' «ادعا»ی مورد اشاره در سؤال مشخص نیست.')
revise(855,'متن می‌گوید اگر مدیریت هزینه نباشد، با افزایش درآمد هزینه‌ها هم افزایش می‌یابند و کیفیت زندگی بهتر نمی‌شود؛',[('متن می‌گوید اگر مدیریت هزینه نباشد، با افزایش درآمد هزینه‌ها هم افزایش می‌یابند و کیفیت زندگی بهتر نمی‌شود.',0,'اگر مدیریت هزینه نباشد با افزایش درآمد هزینه‌ها افزایش یافته و تغییری در کیفیت زندگی ایجاد نمی‌کند.')],lim=' منظور «جایی که پول جا می‌شود» روشن نیست.')
revise(1149,'اگر منظور مثال مسیر علاقه در متن باشد، باید کارهای لازم آن، مثل تایپ برای نوشتن مقاله، را انجام داد حتی اگر خود آن کارها مورد علاقه نباشند؛',[('در مثال علاقه به مقاله‌نوشتن، دوست‌نداشتن تایپ دلیل کنارگذاشتن نوشتن نیست و کارهای لازم مسیر باید انجام شوند.',0,'مثلاً من به مقاله‌نوشتن علاقه دارم، ولی ممکن است از تایپ‌کردن خوشم نیاید. نمی‌شود گفت چون تایپ را دوست ندارم، مقاله هم نمی‌نویسم. بخشی از مسیر علاقه، کارهایی است که باید انجام شوند.')],lim=' سؤال موقعیت موردنظر را مشخص نمی‌کند.',reason='سؤال و تمام ده شاهد عیناً با مورد۱۲۰ یکسان‌اند؛ پاسخ به مثال متن محدود شد و ابهام مرجع برای سازگاری ثبت شد.')
save(w/'previous_checkpoint.json',c);save(w/'previous_audit.jsonl',[aud[d['audit']['candidate_id']] for d in ds],True);save(w/'previous_support.jsonl',[sup[d['audit']['candidate_id']] for d in ds],True);save(w/'revision_decisions.json',ds)
report=[dict(position=pos,category=cat,reason_fa=reason,outcome='RESOLVED' if pos in [2,481] else 'REVIEW_REQUIRED',full_evidence_reread=True) for pos,(cat,reason) in sorted(NOTES.items())]
save(w/'review_recheck_report.json',dict(original_review_count=45,resolved=[2,481],new_review=[1149],notes=report,independent_verification=False))
save(w/'manual_notes.json',{str(k):list(v) for k,v in NOTES.items()})
new=f.append_decisions(copy.deepcopy(s),ds);f.preserve(s,new);f.publish(new,'coordinator_recheck_final_v1',[d['audit']['position'] for d in ds],'تمام۱۱۴۹مورد بررسی شده؛۴۵بازبینی مجدداً خوانده شد،۲حل و۱ابهام مشابه ثبت شد. هیچ مورد بررسی‌نشده باقی نیست.',datetime.now(timezone.utc).isoformat())
save(w/'FINAL_CURRENT.json',f.verify_current()[0]);save(w/'FINAL_COUNTS.json',f.validate(new,i,o))
