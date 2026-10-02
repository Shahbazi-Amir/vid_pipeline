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
    a=decision(348,'تمام ده شاهد خوانده شد. صفر ریسک را عدم دستیابی به منفعت مورد انتظار و انحراف نامطلوب از هدف مطلوب تعریف می‌کند و صریحاً انحراف مطلوب را از بحث جدا می‌گذارد. دوم و هفتم نرسیدن به هدف را تأیید می‌کنند؛ دارایی، بدن و بازارهای مختلف نمونه‌های موضوع خطرند، نه تعریف متفاوت. پاسخ مفهوم را می‌دهد و هر انحراف یا هر نوسان را زیان قطعی نمی‌نامد.',[[(0,'عدم دستیابی به منفعت مورد انتظار','جزء اول تعریف عیناً آمده است.'),(0,'یا این که انحراف نامطلوب از هدف مطلوبم','نامطلوب بودن انحراف از هدف مستقیم است.')]],dimensions={
      'evidence_sufficiency':'هر دو جزء تعریف در صفر و شرح‌های مؤید موجودند.',
      'question_answer_fit':'رابطه مفهومی ریسک با منفعت و هدف پاسخ داده شد؛ فهرست همه دارایی‌ها ادعا نشده.',
      'factual_claim_support':'claim واحد دو جزء پاسخ را پوشش دارد.',
      'scope_modality_negation_quantity':'نامطلوب و مورد انتظار حفظ‌اند؛ انحراف مطلوب و زیان قطعی هر نوسان خلط نشده‌اند.',
      'outside_details':'فرمول اندازه‌گیری ریسک یا آمار بازار از بیرون اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'دارایی و بدن و انواع بازار مثال‌اند؛ تعریف محدود پاسخ با آنها ناسازگار نیست.'})
    ev=json.loads(rows(ROOT/'inputs.jsonl')[348]['messages'][1]['content'])['evidence'];r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[348]['response'])
    r['answer_text']='در توضیح چارچوب شش سرفصل، همه زیر چتر تصمیم‌گیری مالی قرار می‌گیرند؛ در توضیح خطرهای این بخش‌ها، متن چتر مدیریت ریسک و بیمه را هم مطرح می‌کند.'
    r['claims']=[dict(claim_text='در توضیح چارچوب شش سرفصل، همه زیر چتر تصمیم‌گیری مالی قرار می‌گیرند.',claim_type='FACTUAL',evidence_ids=[ev[0]['evidence_id']]),dict(claim_text='متن از منظر در معرض ریسک بودن بخش‌های مالی، مجموعه را زیر چتر مدیریت ریسک و بیمه قرار می‌دهد.',claim_type='FACTUAL',evidence_ids=[ev[3]['evidence_id']])]
    b=decision(349,'تمام ده شاهد خوانده شد. صفر در شرح شش سرفصل همه را زیر چتر تصمیم‌گیری مالی می‌گذارد، اما سوم برای همان بخش‌ها از منظر خطر چتر مدیریت ریسک و بیمه را می‌گوید. پاسخ بی‌قید اولیه فقط یکی را انتخاب کرده و ابهام سؤال کلی را نمی‌گفت. پاسخ فعال دو کاربرد و زمینه هر یک را تفکیک و با دو claim و دو شاهد دوباره بررسی شد. چارچوب‌های چهارحوزه‌ای پژوهش‌ها زمینه متفاوت‌اند؛ حکم طبقه‌بندی یکتای همه ادبیات مالی اضافه نشده است.',[
      [(0,'و در نهایت همه اینها زیر چتر تصمیم‌گیری مالی قرار می‌گیرد.','چتر تصمیم‌گیری در پایان شرح سرفصل‌های همین چارچوب مستقیم است.')],
      [(3,'تمام این بخش‌ها هم در معرض ریسک‌اند؛ ممکن است درآمدمان را از دست بدهیم، قرض‌مان را نتوانیم پرداخت کنیم، سرمایه‌گذاری‌مان آسیب ببیند یا دارایی‌مان در معرض خطر قرار بگیرد. بنابراین کل این مجموعه زیر چتر **مدیریت ریسک و بیمه** قرار می‌گیرد.','چتر دوم به دلیل در معرض ریسک بودن درآمد، قرض، سرمایه و دارایی گفته شده است.')]],repair=r,dimensions={
      'evidence_sufficiency':'هر دو چتر و زمینه در صفر و سوم صریح‌اند.',
      'question_answer_fit':'سؤال کلی با تفکیک دو کاربرد چتر در متن پاسخ داده شد.',
      'factual_claim_support':'دو claim تمام پاسخ و دو زمینه را پوشش می‌دهند.',
      'scope_modality_negation_quantity':'چتر تصمیم‌گیری در چارچوب سرفصل‌ها و چتر ریسک از منظر خطر است؛ هیچ‌یک یگانه در همه منابع نامیده نشده.',
      'outside_details':'سلسله‌مراتب رسمی یا قاعده مفهومی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'دو استفاده متفاوت از چتر در صفر و سوم آشکار شد و با زمینه هر کدام گزارش شد؛ تعارض نادیده گرفته نشده است.'})
    b['audit']['error_categories']=['unresolved evidence ambiguity']
    b['repair']['reason_fa']='پاسخ بی‌قید یکی از دو چتر شواهد را انتخاب کرده بود؛ دو کاربرد با زمینه جدا ثبت شدند.'
    b['repair']['recheck_reason_fa']='هر چتر و زمینه آن با صفر یا سوم و claim متناظر دوباره بررسی شد.'
    c=decision(350,'تمام ده شاهد خوانده شد. صفر تفاوت تصویر ساختگی خواسته و تصویر واقعی را در توضیح گوینده فاقد تمایز ذهنی و موجب تنش می‌داند؛ اول و نهم مثال بنز و پراید و فاصله تصویرها را شرح می‌دهند. پاسخ طبق متن را حفظ کرده و می‌تواند را به جای سبب قطعی به کار می‌برد. نظریه کلی پزشکی یا اثبات تجربی ناتوانی ذهن در همه شرایط ادعا نشده؛ تأیید قانون جذب و رسیدن خودکار به خواسته نیز از پاسخ حذف است.',[[(0,'ذهن بین این دوتا تصویر تمایزی قائل نمی‌شه\nیعنی نمی‌گه خب این که ساختگی بود، اون که واقعی بود','دو تصویر واقعی و ساختگی در شرح منبع مستقیم‌اند.'),(0,'ذهن تمایزی قائل نمی‌شه و این باعث تنش می‌شه','پیامد تنش مستقیم است و پاسخ آن را با انتساب گزارش می‌کند.')]],dimensions={
      'evidence_sufficiency':'صفر هر دو نوع تصویر و پیامد تنش را دارد؛ نهم زمینه خواسته‌ها را شرح می‌دهد.',
      'question_answer_fit':'میان چه چیزهایی تمایز نیست و چه نتیجه‌ای دارد هر دو پاسخ داده شد.',
      'factual_claim_support':'claim واحد تصویرهای واقعی و ساختگی و تنش و انتساب را پوشش دارد.',
      'scope_modality_negation_quantity':'طبق متن و می‌تواند حفظ‌اند؛ ناتوانی پزشکی همگانی تأیید نشده.',
      'outside_details':'قانون جذب، درمان یا سازوکار عصب‌شناسی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'شواهد ناخودآگاه، بازاریابی و فشار مالی علل دیگرند؛ شرح خاص تصویرسازی را نقض نمی‌کنند. صحت مستقل این توضیح ذهنی NOT_EVALUATED است.'})
    return [a,b,c]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==829
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0016';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[348,349,350],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0016/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=36,total_reviewed=832,remaining=317,next_position=351)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_348_350_v1',[348,349,350],'KEEP348 و350 و رفع ابهام349؛ ادامه351.',cp['created_utc'])
