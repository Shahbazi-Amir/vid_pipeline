"""Explicit decisions after full evidence reading; existing validator only."""
import sys, json
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'parallel_v1/shared'))
from decisions_006_010 import decision
import incremental_review as frozen
import range_io
from audit_structure import save,sha

def decisions():
    d315=decision(315,'هر ده شاهد خوانده شد. شاهد صفر نقدشوندگی دارایی را تبدیل سریع آن به پول و نقدشوندگی خود پول را دسترسی متفاوت به اسکناس و حساب‌های پس‌انداز توضیح می‌دهد. پاسخ همین دو معنا را با هم دارد و برتری اسکناس را «از نقدشونده‌ترین» بیان می‌کند؛ پول را دارایی بی‌ریسک یا بدون کاهش ارزش نمی‌نامد. شواهد ملک، سپرده بلندمدت و مبادله با این تعریف سازگارند؛ نرخ‌ها و قانون‌های تاریخی آن‌ها به پاسخ منتقل نشده‌اند.',[[
      (0,'یه که من به‌سرعت بتونم تبدیلش بکنم به پول، راحت وقتی که خرجم می‌خوام برم بفروشمش و پول بگیرم.','سرعت و راحتی تبدیل دارایی به پول، بخش نخست تعریف در claim را پشتیبانی می‌کند.'),
      (0,'اسکناسی که دست شماست شاید نقدشونده‌ترین پوله، ولی ممکنه شما یه حساب پس‌اندازی داشته باشید، یک کمی طول می‌کشه تا بهش دسترسی پیدا بکنید.','نقدشوندگی پول به دسترسی وابسته است و اسکناس با قید شاید بالاتر از حسابی با تأخیر دسترسی قرار گرفته؛ قید «از نقدشونده‌ترین» پاسخ حفظ شده است.')]],dimensions={
      'evidence_sufficiency':'تعریف تبدیل دارایی و مثال دسترسی به خود پول در شاهد صفر کافی است.',
      'question_answer_fit':'تعریف نقدشوندگی پول با توضیح دسترسی و تمایز آن از تبدیل دارایی پاسخ داده شد.',
      'factual_claim_support':'تنها claim هر دو جزء تعریف و مثال اسکناس را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'شاید نقدشونده‌ترین در شاهد به از نقدشونده‌ترین تبدیل شده؛ برتری مطلق همه شکل‌های پول ادعا نشده.',
      'outside_details':'هزینه تبدیل، سود، نرخ روز یا توصیه خرید دارایی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'ابهام اصطلاح نقدشوندگی پول با تمایز تبدیل دارایی و دسترسی به پول رفع شده؛ مثال سپرده بلندمدت مؤید است.'})
    d316=decision(316,'هر ده شاهد خوانده شد. عبارت علت کلاهبرداری زیاد و نفی توصیه در شاهد صفر دقیقاً برای خرید و استفاده از ربات‌های موجود بازار آمده است. پاسخ منع را به طراحی و استفاده از ربات شخصی تعمیم نمی‌دهد؛ شاهد همان ربات شخصی را مناسب معرفی می‌کند. شواهد کانال سیگنال، طلا، پانزی، پراپ و صرافی مصادیق دیگری‌اند و به موضوع ربات پاسخ داده‌شده تعارض ندارند. این گزارش متن است و توصیه مالی جدید تولید نمی‌کند.',[[
      (0,'استفاده از ربات تریدینگ برای استراتژی‌های معاملاتی شخصی گزینۀ مناسبی است، اما خرید ربات و استفاده از ربات‌های رایگان و پولی موجود در بازار به دلیل کلاهبرداری‌های زیاد، به هیچ عنوان توصیه نمی‌شود.','موجود در بازار، رایگان و پولی، و علت کلاهبرداری زیاد دقیقاً بیان شده؛ مقابله با ربات شخصی دامنه منع را محدود می‌کند.')]],dimensions={
      'evidence_sufficiency':'عبارت پرسش با حکم مربوط به ربات‌های بازار در شاهد صفر تطابق مستقیم دارد.',
      'question_answer_fit':'مصادیق دقیق رایگان و پولی بازار مشخص شدند؛ علت در پرسش آمده و در شاهد صریح است.',
      'factual_claim_support':'یک claim تمام محتوای پاسخ و انتساب به متن را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'نفی توصیه برای ربات‌های موجود بازار است؛ ربات شخصی حذف یا ممنوع شمرده نشده.',
      'outside_details':'آمار کلاهبرداری، قانون روز فارکس و توصیه جدید افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'سؤال کلی است اما عبارت به دلیل کلاهبرداری‌های زیاد، شاهد ربات‌ها را مشخص می‌کند؛ مثال‌های دیگر موجب انحصاری خواندن آن نشده‌اند.'})
    d317=decision(317,'هر ده شاهد خوانده شد. شاهد صفر سه حالت نیاز ضروری بدون توان بازپرداخت آینده، نیاز ضروری با توان بازپرداخت و خواسته‌های غیرضروری را جدا می‌کند؛ برای حالت نخست صدقه یا کمک بلاعوض پیشنهاد می‌دهد. پاسخ کوتاه با زمینه سؤال همین حالت را جواب می‌دهد و توصیه را به همه وام‌ها یا قرض‌گیرندگان تعمیم نمی‌دهد. شواهد احکام بازپرداخت، مهلت، مستثنیات دین و تأمین مالی کسب‌وکار شرایط دیگری را بحث می‌کنند و این پیشنهاد را نقض نمی‌کنند.',[[
      (0,'اگر فردی برای تأمین نیازهای ضروری‌اش پولی لازم داشت و در آینده هم توان بازپرداخت آن را نخواهد داشت، بهتر است در قالب صدقه یا کمک بلاعوض مبلغ موردنظر را تأمین کنیم.','شرط نیاز ضروری و ناتوانی بازپرداخت آینده همراه با هر دو گزینه صدقه و کمک بلاعوض تصریح شده؛ جایگزینی قرض در همان تفکیک سه‌گانه شاهد معنا دارد.')]],dimensions={
      'evidence_sufficiency':'راهکار پیشنهادی برای همان دو شرط سؤال در شاهد صفر مستقیم است.',
      'question_answer_fit':'پاسخ به شیوه تأمین مبلغ می‌پردازد، نه حکم دریافت وام یا فروش ضروریات.',
      'factual_claim_support':'claim تنها، هر دو گزینه صدقه و کمک بلاعوض و نفی توان بازپرداخت را پوشش دارد.',
      'scope_modality_negation_quantity':'ناتوانی بازپرداخت در زمینه نیاز ضروری سؤال حفظ شده؛ حکم انحصاری یا الزام عمومی ساخته نشده.',
      'outside_details':'هیچ مبلغ، شرط شرعی یا قانون بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'قرض‌الحسنه در حالت توان بازپرداخت و عقود در حالت خواسته است؛ با حالت مورد سؤال خلط نشده.'})
    return [d315,d316,d317]

if __name__=='__main__':
    work=Path(__file__).resolve().parent
    ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    current,previous=frozen.verify_current()
    assert current['semantic_complete']==796
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state)
    directory=work/'batches/batch_0001';assert not directory.exists();directory.mkdir(parents=True)
    save(directory/'decisions.jsonl',ds,True)
    for name,records in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[])]:save(directory/name,records,True)
    counts=frozen.validate(state,ins,outs)
    save(directory/'validation.json',dict(**counts,schema='PASS',revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit='65b618ab92fb9e1ec7741faa9210f6a1de50f647',base_snapshot='checkpoints/consolidated_796_20261002',base_reviewed=796,positions=[315,316,317],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat(),previous_batches=[])
    save(directory/'checkpoint.json',cp)
    reloaded=[json.loads(l) for l in (directory/'decisions.jsonl').read_text().splitlines()]
    assert frozen.validate(frozen.append_decisions(previous,reloaded),ins,outs)==counts
    save(work/'CURRENT.json',dict(owner='coordinator',base_commit=cp['base_commit'],base_reviewed=796,batches=[dict(path='batches/batch_0001/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes()))],completed_candidate_ids=cp['candidate_ids'],new_reviewed=3,total_reviewed=799,remaining=350,next_position=318,import_ready=False))
    frozen.publish(state,'coordinator_resume_315_317_v1',[315,317],'ادامه سریالی هماهنگ‌کننده؛ سه KEEP جدید؛ delta قابل بازسازی در coordinator/resume_v1؛ ممیزان قبلی تغییر نکردند.',cp['created_utc'])
