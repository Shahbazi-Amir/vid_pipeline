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
    a=decision(346,'تمام ده شاهد خوانده شد. صفر مراجعه بعد از سی روز را فقط با عذر موجه و تأیید هیئت حل اختلاف تا سه ماه مجاز می‌داند. پاسخ هر دو شرط و سقف زمانی را با انتساب به متن دارد؛ پذیرش قطعی مستمری یا سه ماه پس از پایان سی روز ادعا نمی‌کند. شواهد خانه، ترک کار، ثبت هزینه و بیمه عمر درباره همین مهلت نیستند. این بررسی تطبیق با متن است و اعتبار قانون امروز را تعیین نمی‌کند.',[[(0,'مراجعۀ متقاضی بعد از سی روز، فقط با عذر موجه و با تأیید هیأت حل اختلاف ادارۀ تعاون، کار و رفاه اجتماعی تا سه ماه امکان‌پذیر است.','دو شرط لازم و سقف سه ماه برای همان مراجعه مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'همه شروط و سقف زمانی در صفر صریح‌اند.',
      'question_answer_fit':'شرایط مراجعه پس از سی روز پاسخ داده شده است.',
      'factual_claim_support':'claim واحد هر دو شرط، سقف و انتساب را پوشش دارد.',
      'scope_modality_negation_quantity':'و بین شروط حفظ است؛ تا سه ماه سقف است نه سه ماه اضافه بعد از سی روز.',
      'outside_details':'قانون جاری یا تضمین تصویب درخواست از بیرون افزوده نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'منظور مراجعه بیمه بیکاری در صفر روشن است؛ مهلت اجاره و مرخصی در سایر شواهد موضوع متفاوت دارند.'})
    b=decision(347,'تمام ده شاهد خوانده شد. صفر گزارش منتسب به اکونومیست را درباره هشتاد درصد تصمیم خرید مصرف‌کنندگان می‌گوید؛ اول همین مقدار و سوم تعبیر هزینه زندگی را نقل می‌کند. پاسخ گزارش نقل‌شده را حفظ می‌کند و نه آمار جاری همه زنان یا سهم زن‌ها از درآمد و کل هزینه پولی را. بیست‌وپنج درصد دستمزد، هفتاد درصد تخفیف، نصف جمعیت و پنجاه‌ودو درصد اعتمادبه‌نفس متغیرهای دیگرند.',[[(0,'به نوشته روزنامه اکونومیست، بررسی‌ها نشان می‌دهند که 80 درصد تصمیم‌گیری‌های خرید مصرف‌کنندگان، از مراقبت‌های پزشکی گرفته تا مسکن، اثاثیه و خوراک توسط زنان انجام می‌گیرد.','عدد، متغیر تصمیم خرید و انتساب گزارش همگی مستقیم‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر مقدار و مخرج و انتساب را مستقیم دارد.',
      'question_answer_fit':'درصد تصمیم‌های خرید مورد سؤال پاسخ داده شد.',
      'factual_claim_support':'claim کوتاه در زمینه سؤال مقدار منتسب به گزارش را پوشش دارد.',
      'scope_modality_negation_quantity':'هشتاد درصد تصمیم خرید در گزارش است؛ نه درصد درآمد یا مقدار کل خرج و نه آمار فعلی تأییدشده.',
      'outside_details':'سال، کشور و دامنه آماری خارج از متن اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'تعبیر هزینه زندگی در سوم مخرج مبهم‌تر دارد؛ پاسخ با سؤال و عبارت دقیق تصمیم خرید در صفر تطبیق دارد. سایر درصدها شاخص متفاوت‌اند.'})
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==827
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0015';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[346,347],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0015/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=33,total_reviewed=829,remaining=320,next_position=348)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_346_347_v1',[346,347],'دو KEEP346 و347؛ ادامه348.',cp['created_utc'])
