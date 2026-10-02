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
    a=decision(343,'تمام ده شاهد خوانده شد. صفر هر چهار علامت خواب و اشتها را در برخی افراد زیر فشار مالی بیان می‌کند. پاسخ رابطه ممکن را حفظ می‌کند، نه تشخیص پزشکی یا سبب قطعی همه مشکلات خواب و خوردن. دوم علائم دیگری هم دارد و صفر مشکلات جسمی دیگری را می‌گوید؛ پاسخ مدعی فهرست کامل نیست. سایر پژوهش‌ها ارتباط مالی و روان را بررسی می‌کنند و چهار علامت پاسخ را نقض نمی‌کنند.',[[(0,'در شرایط فشار مالی، بعضی آدم‌ها از استرس پرخوری یا پرخوابی می‌کنند و بعضی‌ها برعکس کم‌اشتهایی و کم‌خوابی پیدا می‌کنند.','هر چهار نشانه، بعضی افراد و زمینه فشار مالی مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر هر چهار علامت پاسخ را مستقیم دارد.',
      'question_answer_fit':'چند نشانه مرتبط پاسخ داده شده؛ جامعیت همه علائم ادعا نشده.',
      'factual_claim_support':'claim واحد تمام چهار مورد و امکان همراهی را پوشش دارد.',
      'scope_modality_negation_quantity':'می‌تواند و یا حفظ‌اند؛ هر فرد الزاماً هر چهار نشانه ندارد.',
      'outside_details':'تشخیص، نسخه درمان و ادعای پزشکی بیرونی افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'علائم جسمی و روانی دیگر مکمل‌اند؛ استعاره سرطان در صفر به سرطان واقعی تعبیر نشده.'})
    b=decision(344,'تمام ده شاهد خوانده شد. صفر، دوم و پنجم همراهی علم و احساس را کمک‌کننده به رفتار می‌دانند. اول مشوق و جریمه، چهارم باورها و ششم و هفتم تلنگر را نیز عوامل هدایت رفتار می‌گویند. سؤال کلی است اما پاسخ یک عامل ممکن می‌دهد و انحصار یا علت واحد را ادعا نمی‌کند؛ شکل‌گیری رفتار را مساوی تضمین رفتار مطلوب یا درست نکرده است.',[[(0,'بُعد احساسی شما باید تقویت شود. این بُعد سوم وجود شماست؛ بُعد احساسی که باید با بُعد علمی گره بخورد. وقتی این دو به هم گره بخورند، می‌توانند معجزه کنند و می‌توانند رفتار شکل بدهند.','گره‌خوردن دو بعد علمی و احساسی و امکان شکل‌دادن رفتار مستقیم است؛ استعاره معجزه در پاسخ نیامده است.')]],dimensions={
      'evidence_sufficiency':'صفر رابطه را مستقیم دارد و دوم و پنجم آن را شرح می‌دهند.',
      'question_answer_fit':'یک عامل ممکن برای رفتار ارائه شده؛ سؤال تنها عامل یا فهرست همه عوامل نمی‌خواهد.',
      'factual_claim_support':'claim واحد گره‌خوردن دانش و احساس و امکان کمک را پوشش دارد.',
      'scope_modality_negation_quantity':'می‌تواند کمک کند حفظ شده؛ تضمین رفتار یا درستی دانش و رفتار نیست.',
      'outside_details':'سازوکار عصب‌شناسی یا علت انحصاری اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'مشوق، جریمه، باور، تلنگر و محیط عوامل دیگرند؛ پاسخ وجود آنها را نفی نمی‌کند و مرجع نامعلوم را قطعی تعیین نمی‌کند.'})
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[344]['response'])
    r['answer_text']='متن اهمیت سواد مالی را به اندازهٔ غذا خوردن و تمام روزهای زندگی می‌داند؛ برای بهبود تصمیم و رفتار مالی، آموزش دانش و سپس تجربهٔ آن را لازم می‌شمارد.'
    r['claims'][0]['claim_text']=r['answer_text']
    c=decision(345,'تمام ده شاهد خوانده شد. پاسخ اولیه فایده و آموزش را داشت اما مقایسه میزان اهمیت که سؤال می‌خواهد و صفر مستقیم بیان می‌کند حذف شده بود. مقایسه غذا و روزهای زندگی با انتساب صریح به متن افزوده شد و پاسخ و claim فعال با سه بخش صفر دوباره بررسی شدند. شواهد گروه‌های هدف، آموزش زودهنگام و ضرورت در شرایط پیچیده مؤید اهمیت‌اند؛ صحت انتساب بیرونی یونسکو و تضمین ثروتمندشدن از آنها استنتاج نشده است.',[[(0,'سواد مالی به اندازۀ غذا خوردن مهم است.','مقایسه اهمیت در منبع مستقیم و در پاسخ به متن منتسب است.'),(0,'اهمیت سواد مالی به اندازۀ اهمیت تمام روزهایی است که زندگی می‌کنیم','مقایسه با تمام روزهای زندگی مستقیم است.'),(0,'آموزش سواد مالی نیازمند کسب دانش و در مرحلۀ بعد، تجربۀ آن دانش است.','دو مرحله دانش و تجربه به همان ترتیب‌اند.'),(0,'سواد مالی مجموعه‌ای از دانش‌ها، نگرش‌ها و توانایی‌ها برای بهبود تصمیم‌ها و رفتارهای مالی است.','هدف بهبود تصمیم و رفتار مالی مستقیم آمده است.')]],repair=r,dimensions={
      'evidence_sufficiency':'مقایسه و فایده و مراحل آموزش همه در صفر مستقیم‌اند.',
      'question_answer_fit':'میزان اهمیت که در اصل حذف شده بود با مقایسه منتسب به متن تکمیل شد.',
      'factual_claim_support':'claim فعال همه مقایسه، فایده و دو مرحله پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'قیاس غذا و روزهای زندگی دیدگاه متن است؛ رتبه علمی یا تضمین نتیجه قطعی معرفی نشده.',
      'outside_details':'تأیید یونسکو یا سود مالی عددی و برنامه آموزشی بیرونی افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'هشتم پدران بدون دانش رسمی را می‌پذیرد و ضرورت امروز را می‌گوید؛ پاسخ نفی همه تجربه‌های موفق بدون آموزش رسمی ندارد.'})
    c['audit']['error_categories']=['incomplete question coverage']
    c['repair']['reason_fa']='مقایسه میزان اهمیت در جواب سؤال حذف شده بود؛ با انتساب به متن افزوده شد.'
    c['repair']['recheck_reason_fa']='مقایسه غذا و روزهای زندگی و فایده و ترتیب دانش و تجربه با صفر دوباره بررسی شدند.'
    return [a,b,c]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==824
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0014';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[343,344,345],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0014/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=31,total_reviewed=827,remaining=322,next_position=346)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_343_345_v1',[343,344,345],'دو KEEP343 و344 و اصلاح345؛ ادامه346.',cp['created_utc'])
