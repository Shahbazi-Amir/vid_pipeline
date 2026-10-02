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
    a=decision(359,'تمام ده شاهد خوانده شد. صفر ابزار بودجه‌بندی و مبنای تجربه هزینه‌های سه ماه گذشته برای تخصیص ماه چهارم را صریح دارد. پاسخ هر دو بخش سؤال را دارد و ادعا نمی‌کند این تجربه تنها عامل بودجه در همه شرایط است؛ شواهد درآمد مطمئن و اهداف و اولویت‌ها مکمل‌اند. ثبت هزینه و دسته‌بندی در دوم و سوم مراحل پیشین‌اند، نه جایگزین ابزار و مبنای سؤال.',[[(0,'حالا می‌توانیم از ابزار بودجه‌بندی برای کنترل هزینه‌ها استفاده کنیم. با توجه به حال و هوای سه ماه گذشته، بنویسیم در ماه چهارم چه هزینه‌هایی خواهیم داشت و بر اساس تجربه هزینه‌‌های سه ماه گذشته، مبلغی را برای هر یک مشخص کنیم.','نام ابزار و مبنای تعیین هر مبلغ در همین برنامه صریح است.')]],dimensions={
      'evidence_sufficiency':'صفر هر دو بخش ابزار و مبنا را مستقیم دارد.',
      'question_answer_fit':'بودجه‌بندی و مبنای مبالغ هر ردیف هر دو پاسخ داده شدند.',
      'factual_claim_support':'claim واحد تمام ابزار و مبنا و سه ماه را پوشش دارد.',
      'scope_modality_negation_quantity':'سه ماه گذشته مبنای این برنامه است؛ انحصار مبنا و دستور ثابت همه بودجه‌ها ادعا نشده.',
      'outside_details':'درصد یا روش محاسبه آماری بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'درآمد قابل اطمینان و اهداف و اولویت‌ها در دیگر شواهد مکمل‌اند؛ مبنای تجربه را نقض نمی‌کنند.'})
    b=decision(360,'تمام ده شاهد خوانده شد. صفر مدیریت دخل‌وخرج، بودجه‌بندی، ارزش دارایی و تجربه مسئولیت‌پذیری را مستقیم نام می‌برد. اول و سوم و شواهد پرداخت متناسب با سن نقش تجربه شخصی و محدودیت منابع را شرح می‌دهند. پاسخ تجربه را می‌گوید نه تضمین یادگیری کامل و بی‌نیازی از همراهی والدین؛ کشف استعداد ناشی از کار در دوم و هشتم به پول‌توجیبی نسبت داده نشده است.',[[(0,'دریافت پول توجیبی به کودکان مدیریت دخل‌وخرج، بودجه‌بندی و درک ارزش دارایی‌ها را می‌آموزد.\nتجربه مسئولیت‌پذیری را به همراه دارد.','هر چهار جزء تجربه در دو جمله متوالی صریح‌اند.')]],dimensions={
      'evidence_sufficiency':'صفر تمام چهار تجربه را مستقیم دارد و سایر شواهد مؤیدند.',
      'question_answer_fit':'تجربه‌هایی که پول‌توجیبی فراهم می‌کند پاسخ داده شدند.',
      'factual_claim_support':'claim واحد تمام چهار مؤلفه متن پاسخ را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'تجربه آموزشی است؛ تضمین نتیجه همه پرداخت‌ها یا هر مبلغی نیست.',
      'outside_details':'سن آغاز ثابت، مبلغ مناسب یا نسخه تربیتی بیرونی اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'پرداخت نامتناسب می‌تواند در اول آسیب بدهد؛ تجربه درست در سوم همراهی می‌خواهد. پاسخ این شروط را نفی نکرده و اثر کار را با پول‌توجیبی خلط نکرده است.'})
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==840
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0019';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[359,360],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0019/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=46,total_reviewed=842,remaining=307,next_position=361)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_359_360_v1',[359,360],'دو KEEP359 و360؛ ادامه361.',cp['created_utc'])
