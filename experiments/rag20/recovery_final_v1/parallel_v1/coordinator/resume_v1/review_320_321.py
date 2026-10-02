"""Full-evidence decisions for positions 320–321."""
import sys,copy,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'parallel_v1/shared'))
from decisions_006_010 import decision
from audit_structure import rows,save,sha
import incremental_review as frozen
import range_io

def decisions():
    d320=decision(320,'تمام ده شاهد خوانده شد. شاهد صفر در نتایج پژوهش دانش‌آموزان، اثر مثبت و معنادار ارزش‌های اخلاقی بر رابطه سواد و رفتار مالی و افزایش اثر سواد مالی با پایبندی اخلاقی را بیان می‌کند. پاسخ به پژوهش نقل‌شده مقید است و آن را قانون علّی همگانی یا نتیجه مستقل تأییدشده نمی‌نامد. شواهد اخلاق معامله، ارزش‌محوری و سرمایه‌گذاری اخلاقی سازگارند؛ ادعاهای مطلق یا تاریخی شاهد چهارم به پاسخ اضافه نشده‌اند.',[[
      (0,'3- ارزش‌های اخلاقی بر رابطۀ بین سواد مالی و رفتار مالی تأثیر مثبت و معناداری دارد؛\nپایبندی به ارزش‌های اخلاقی تأثیر سواد مالی بر رفتار مالی را افزایش می‌دهد.','تقویت اثر سواد مالی بر رفتار با پایبندی اخلاقی در نتایج همین پژوهش صریح است؛ انتساب پژوهش دامنه پاسخ را محدود نگه می‌دارد.')]],dimensions={
      'evidence_sufficiency':'نتیجه سوم پژوهش نقل‌شده مستقیماً رابطه مورد سؤال را بیان می‌کند.',
      'question_answer_fit':'نقش تقویت‌کننده اخلاق در رابطه سواد و رفتار مالی پاسخ داده شده.',
      'factual_claim_support':'تنها claim تقویت اثر و انتساب پژوهش را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'قید پژوهش نقل‌شده مانع تبدیل نتیجه دانش‌آموزان به حکم مستقل تمام جوامع است.',
      'outside_details':'اندازه اثر، نمونه آماری، علیت مستقل یا توصیه سرمایه‌گذاری افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'شواهد دیگر جنبه اخلاقی تصمیم مالی را بسط می‌دهند؛ هیچ‌یک نتیجه محدود نقل‌شده را نقض نمی‌کند.'})
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[320]['response'])
    r['answer_text']='طبق دیدگاه این متن، ادارهٔ جامعه باید بر توسعهٔ اقتصادی تکیه کند، نه زهد.'
    r['claims'][0]['claim_text']=r['answer_text']
    d321=decision(321,'تمام ده شاهد خوانده شد. شاهد صفر عنوان اداره جامعه بر اساس توسعه اقتصادی و نه زهد را دارد و توضیح می‌دهد کشور را نمی‌توان با زهد اداره کرد، هرچند سخنرانی و آموزش زهد منع نشده است. پاسخ اولیه این دیدگاه را بی‌انتساب به صورت حکم عمومی می‌گفت و واژه تحمیل عمومی به آن می‌افزود. اصلاح به دیدگاه همین متن مقید شد و همان تقابل توسعه اقتصادی و زهد را نگه داشت. نسخه فعال دوباره با عنوان و شرح شاهد تطبیق شد؛ شواهد بازار، دولت و مالیات مدل‌های دیگری از اداره‌اند و به حکم انحصاری همگانی تبدیل نشده‌اند.',[[
      (0,'اداره جامعه بر اساس توسعه اقتصادی و نه زهد','عنوان شاهد دقیقاً هر دو سوی تقابل توسعه اقتصادی و زهد را دارد؛ پاسخ فعال آن را دیدگاه متن می‌نامد.'),
      (0,'جلوی آن زهد هم که در سخنرانی‌ها و کتاب‌ها گفته می‌شود، گرفته نشده اما کشور را نمی‌توان با آن اداره کرد.','شاهد زهد فردی یا بیان آن را ممنوع نمی‌کند و آن را شیوه اداره کشور نمی‌داند؛ این محدودیت در پاسخ فعال حفظ شده است.')]],repair=r,dimensions={
      'evidence_sufficiency':'عنوان و شرح شاهد صفر برای گزارش دیدگاه اداره مبتنی بر توسعه اقتصادی کافی‌اند.',
      'question_answer_fit':'پرسش کلی در چارچوب شاهد مرتبط پاسخ داده شد؛ انتساب صریح جلوی ادعای یک پاسخ جهانی را می‌گیرد.',
      'factual_claim_support':'claim فعال تمام پاسخ را با انتساب و دو سوی تقابل پوشش می‌دهد.',
      'scope_modality_negation_quantity':'دیدگاه متن درباره اداره جامعه است؛ زهد شخصی یا تعلیم آن ممنوع خوانده نشده.',
      'outside_details':'واژه تفسیری تحمیل عمومی حذف شد؛ سیاست یا حکم بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'دیگر شواهد تخصیص بازار و دولت و خدمات مالیاتی را توضیح می‌دهند؛ پاسخ صرفاً دیدگاه شاهد صفر را گزارش می‌کند.'})
    d321['audit']['error_categories']=['missing viewpoint attribution','unsupported scope wording']
    d321['repair']['reason_fa']='دیدگاه یک متن به صورت حکم عمومی و با تعبیر تحمیل زهد عمومی ارائه شده بود؛ انتساب افزوده و تعبیر به تقابل خود شاهد محدود شد.'
    d321['repair']['recheck_reason_fa']='پاسخ و claim فعال دوباره با عنوان توسعه اقتصادی و نه زهد و شرح عدم منع سخنرانی و کتاب بررسی شدند؛ هیچ منع زهد شخصی یا ادعای مستقل عمومی باقی نمانده است.'
    return [d320,d321]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==801
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0003';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[320,321],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0003/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=7,total_reviewed=803,remaining=346,next_position=322)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_320_321_v1',[320,321],'دو مورد جدید؛ 321 با محدودکردن انتساب و دامنه اصلاح و بازبینی شد؛ delta کوچک coordinator/resume_v1.',cp['created_utc'])
