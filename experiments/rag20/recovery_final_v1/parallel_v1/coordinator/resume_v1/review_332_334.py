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
    reason='تمام ده شاهد خوانده شد. پول اضافه در سؤال معلوم نیست اضافه پول‌توجیبی کودک، درآمد دوم برای صندوق اضطراری یا مازاد درآمد برای هدف و دارایی است. شواهد صفر، اول، چهارم و پنجم درباره کسب درآمد بیشتر کودک، سوم درباره برنامه هدف، ششم و نهم درباره اختصاص درآمد دوم به صندوق اضطراری و هفتم و هشتم درباره سرمایه‌گذاری‌اند. بدون وضعیت و هدف، انتخاب دستور واحد از این گزینه‌ها مجاز نیست. پاسخ فقط ابهام همین سؤال را بیان می‌کند؛ نه نبود هر پیشنهاد در شواهد.'
    answer=rows(ROOT/'outputs.jsonl')[331]['response']['answer_text']
    a=decision(332,reason,[],dimensions={
      'evidence_sufficiency':'برای چند موقعیت دستور وجود دارد؛ برای تعیین موقعیت پول اضافه در سؤال کافی نیست.',
      'question_answer_fit':'امتناع از تعیین تکلیف واحد متناسب با ابهام زمینه است.',
      'factual_claim_support':'کل پاسخ محدودیت زمینه است و گزاره مالی تازه ندارد؛ claims خالی درست است.',
      'scope_modality_negation_quantity':'نامشخص بودن مورد سؤال نفی همه پیشنهادهای منابع نیست.',
      'outside_details':'سن، بدهی، صندوق، مبلغ یا هدف کاربر حدس زده نشده.',
      'abstention_justified':'JUSTIFIED',
      'ambiguity_conflict':'چند تخصیص متفاوت بسته به هدف و نوع درآمد در شواهد آمده؛ سؤال یکی را مشخص نمی‌کند.'},units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)])
    a['audit']['status']='VALID_ABSTENTION';a['support']['abstention_review']='JUSTIFIED'
    b=decision(333,'تمام ده شاهد خوانده شد. مرجع این اپلیکیشن در سؤال مشخص نیست و شواهد مانی‌کوچ، مانکی، زیپاد و موزه را شامل می‌شوند. پاسخ با شرط اگر منظور مانی‌کوچ است این ابهام را حفظ کرده و فقط چند قابلیت بودجه همان برنامه را می‌گوید، نه فهرست کامل تمام قابلیت‌ها یا قابلیت اپ‌های دیگر. شاهد صفر هر چهار نوع بودجه و شخصی‌سازی را مستقیم دارد و اول هویت مانی‌کوچ و قابلیت را تأیید می‌کند.',[[(0,'شده و تعریف گروه‌های بودجه به شکل ماهانه یا روزانه در اپلیکیشن وجود دارد. همچنین با اعلام متوسط هزینۀ ماهانه به مانی‌کوچ، بودجه‌ای شخصی‌سازی‌شده از اپلیکیشن ارائه می‌شود که به پس‌انداز پول در هر ماه کمک زیادی می‌کند. به علاوه، امکان تعریف بودجه برای موقعیت‌های خاص، مانند سفر کاری و تعطیلات وجود دارد.','بودجه روزانه، ماهانه، شخصی‌سازی، سفر و تعطیلات مستقیم برای مانی‌کوچ آمده‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر تمام قابلیت‌های محدود پاسخ را دارد؛ اول هویت برنامه را روشن می‌کند.',
      'question_answer_fit':'پاسخ شرطی به ویژگی‌ها داده و تعیین قطعی مرجع نامعلوم نکرده است.',
      'factual_claim_support':'claim واحد تمام قابلیت‌های نام‌برده و شرط مانی‌کوچ را پوشش دارد.',
      'scope_modality_negation_quantity':'شرط اگر منظور مانی‌کوچ است حفظ است؛ ادعای جامعیت یا ویژگی نسخه فعلی ندارد.',
      'outside_details':'نسخه، هزینه اشتراک یا سازگاری دستگاه از بیرون اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'وجود چند اپ مرجع یکتا نمی‌دهد؛ پاسخ به‌صورت صریح شرطی است و قابلیت مانکی و زیپاد را خلط نمی‌کند.'})
    c=decision(334,'تمام ده شاهد خوانده شد. صفر و ششم صریحاً فلسفه داشتن را به خرید زیاد مرتبط می‌کنند؛ اول تصاحب چیزهای حتی بی‌مصرف و سایر شواهد ترتیب داشتن پیش از بودن را شرح می‌دهند. پاسخ می‌تواند را حفظ کرده و ادعا نمی‌کند همه خریداران یا هر خریدی الزاماً ناشی از همین فلسفه است. داستان شرکت و ورزش نمونه‌اند و نتیجه عمومی قطعی از آنها اضافه نشده.',[[(0,'فلسفه داشتن خیلی وقت‌ها ما رو به سمت خریدهای زیاد می‌بره.','رابطه با خرید زیاد در متن مستقیم است؛ می‌تواند از خیلی وقت‌ها قوی‌تر نیست.')]],dimensions={
      'evidence_sufficiency':'رابطه فلسفه داشتن و خرید زیاد در صفر و ششم صریح است.',
      'question_answer_fit':'اثر بر میزان خرید پاسخ داده شد.',
      'factual_claim_support':'claim واحد همه متن پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'می‌تواند حکم همگانی، قطعی یا تک‌علتی ندارد.',
      'outside_details':'آمار خرید یا تبیین روان‌شناختی خارج از متن اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'خرید ناشی از بازاریابی و الگوهای دیگر مکمل بحث‌اند و ادعای محدود امکان اثر را نقض نمی‌کنند.'})
    return [a,b,c]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==813
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0009';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[332,333,334],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0009/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=20,total_reviewed=816,remaining=333,next_position=335)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_332_334_v1',[332,333,334],'امتناع موجه332 و دو KEEP333 و334؛ ادامه335.',cp['created_utc'])
