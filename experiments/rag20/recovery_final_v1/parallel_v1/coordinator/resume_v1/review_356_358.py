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
    a=decision(356,'تمام ده شاهد خوانده شد. صفر پوشش بیمه را میزان تعهد جبران خسارت بیمه‌گر تعریف می‌کند و دوم همین معنا را از مبلغ حق بیمه و سهم پرداخت خود فرد جدا می‌کند. پاسخ فقط تعریف پوشش است، نه تضمین جبران همه خسارت‌ها یا پوشش قانونی نوع خاص امروز. شواهد بیمه عمر و بازنشستگی نمونه‌های تعهد قراردادی‌اند و تعریف را نقض نمی‌کنند.',[[(0,'پوشش بیمه:میزانی که بیمه‌گر متعهد به جبران خسارت است.','تعریف پاسخ عین عبارت پوشش بیمه در متن است.')]],dimensions={
      'evidence_sufficiency':'تعریف صفر صریح است و دوم آن را تأیید می‌کند.',
      'question_answer_fit':'معنای اصطلاح پوشش بیمه پاسخ داده شد.',
      'factual_claim_support':'claim واحد تمام پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'میزان تعهد بیمه‌گر است؛ نه لزوم پرداخت تمام خسارت و نه سهم بیمه‌گذار.',
      'outside_details':'نوع بیمه، سقف عددی یا قانون جاری افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'حق بیمه و فرانشیز در صفر و دوم متفاوت‌اند؛ پوشش جمعیت در سایر زمینه‌ها با این تعریف قراردادی خلط نشده است.'})
    b=decision(357,'تمام ده شاهد خوانده شد. صفر چرخه اول درآمد به هزینه را رسم و خرج مستقیم پول و نبود پشتوانه با تکرار این الگو و قطع درآمد را صریح می‌گوید. پاسخ همان چرخه را شرح می‌دهد، نه فقدان پشتوانه همه کسانی که یک بار خرج کرده‌اند. چرخه‌های دارایی در صفر و هفتم بدیل‌اند؛ صورت سود و زیان و نقطه سربه‌سر کسب‌وکار در دوم درباره همان چرخه نیستند.',[[(0,'درآمد → هزینه.\n\nپول میاد و مستقیم خرج می‌شه. اگر این الگو دائم تکرار بشه، من هر ماه باید از نو کار کنم و اگر درآمد قطع بشه چیزی پشتش نیست.','تعریف چرخه ساده و پیامد تکرار همین چرخه مستقیم است.')]],dimensions={
      'evidence_sufficiency':'صفر چرخه و پیامد آن را مستقیم دارد.',
      'question_answer_fit':'درآمد به هزینه و نبود حلقه پشتوانه در همین چرخه توضیح داده شد.',
      'factual_claim_support':'claim واحد هر دو بخش پاسخ را پوشش دارد.',
      'scope_modality_negation_quantity':'شرح الگوی چرخه ساده تکرارشونده است؛ حکم همه اشخاصی که خرجی می‌کنند نیست.',
      'outside_details':'تضمین بازده یا میزان سرمایه لازم اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'چرخه دارایی درآمدزا بدیل است؛ گزارش حسابداری و بهره مرکب شواهد دیگر چرخه اول را نقض نمی‌کنند.'})
    c=decision(358,'تمام ده شاهد خوانده شد. صفر ترکیب متمایز نمی‌شود و نباید نادیده گرفت را برای تجربه چنددهه‌ای دنیا در آموزش، پژوهش و ترویج سواد مالی به کار می‌برد. پاسخ همین موضوع و سه فعالیت را دارد؛ تأیید همه محصولات جهانی یا ترجمه بی‌چون‌وچرای همه متون را ادعا نمی‌کند. سایر شواهد ابعاد مالی ازدواج و جایگاه مادر را نادیده‌گرفتنی نمی‌دانند، اما ترکیب دقیق سؤال به بند تجربه جهانی در صفر اشاره دارد؛ انحصار همه امور مهم هم ادعا نشده است.',[[(0,'تجربۀ چنددهه‌ای دنیا در موضوع\nسواد مالی\nبرای آموزش، پژوهش و ترویج با انواع محصولات و خدمات را نمی‌شود و نباید نادیده گرفت.','موضوع تجربه دنیا، مدت چنددهه و سه فعالیت و ترکیب نمی‌شود و نباید مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'عبارت دقیق پرسش برای موضوع تجربه جهانی در صفر صریح است.',
      'question_answer_fit':'آنچه نمی‌شود و نباید نادیده گرفت با موضوع و فعالیت‌هایش پاسخ داده شد.',
      'factual_claim_support':'claim واحد تمام تجربه چنددهه‌ای و سه فعالیت پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'چنددهه و جهانی حفظ‌اند؛ دستور تأیید همه ادعاهای جهانی یا انحصار اهمیت نیست.',
      'outside_details':'نام کشور، پژوهش یا اعتبار بیرونی و نقل قول کتاب تاریخی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'نادیده نگرفتن ابعاد ازدواج و نقش مادر در شواهد دیگر موضوع دیگری دارد؛ عبارت متمایز سؤال در صفر با تجربه جهانی منطبق است.'})
    return [a,b,c]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==837
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0018';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[356,357,358],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0018/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=44,total_reviewed=840,remaining=309,next_position=359)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_356_358_v1',[356,357,358],'سه KEEP356–358؛ ادامه359.',cp['created_utc'])
