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
    a=decision(661,'تمام ده شاهد خوانده شد. صفر چهار مرحله بخش دوم کتاب را با پیش‌دبستانی و سه بازه1تا4 و5تا8 و9تا12 می‌گوید. پاسخ هر چهار مرحله و مرزها را دقیق حفظ می‌کند. بخش دوم ابزارهای تمرین کتاب زنان در ششم کتاب دیگری است؛ چهارموضوع بخشش و سرمایه‌گذاری و پس‌انداز و خرج در اول مراحل تحصیلی نیستند و مخلوط نشده‌اند. پنجم و نهم استانداردهای سن‌محور را تأیید می‌کنند.',[[(0,'پیش\u200cدبستانی\nاز سال اول تا پایان سال چهام\nاز سال پنجم تا پایان سال هشتم\nاز سال نهم تا پایان سال دوازدهم.','هر چهار مقطع کامل و با مرزهای سؤال مستقیم‌اند؛ چهام غلط نوشتاری چهارم در بازه است.')]])
    data=json.loads(rows(ROOT/'inputs.jsonl')[661]['messages'][1]['content'])
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[661]['response'])
    r['answer_text']='در تقسیم‌بندی متن، بیمه درمانی در گروه بیمه‌های شخصی است؛ نوع درمان تکمیلی برای هزینه‌های درمانی فراتر از پوشش بیمه پایه معرفی شده است.'
    r['claims'][0]['claim_text']=r['answer_text'];r['claims'][0]['evidence_ids']=[data['evidence'][i]['evidence_id'] for i in [0,1]]
    b=decision(662,'تمام ده شاهد خوانده شد. سؤال بیمه درمانی را به طور عام می‌پرسد اما پاسخ قبلی فقط نوع تکمیلی را می‌گفت. اول درمان بیماری را در شخصی می‌آورد و سپس تکمیلی را جدا می‌کند؛ صفر تعریف پوشش تکمیلی را دارد. پاسخ ابتدا گروه عام در چارچوب متن و سپس تعریف نوع تکمیلی را می‌گوید. بیمه پایه اجتماعی و چارچوب بازرگانی در شواهد‌اند؛ از تعمیم همه بیمه‌های درمانی به اختیاری و تضمین پوشش کامل هزینه‌ها پرهیز شده است. تفاوت شمار سه و چهار نوع در پاسخ نیامده است.',[[(1,'بیمه های شخصی چهار نوعه\nیکی این که مثلا من بیمار بشم می\u200cشه\nبیمه در واقع اون بیماری درمانی','در چارچوب این متن، درمان بیماری در گروه شخصی معرفی شده است.'),(0,'بیمۀ درمان تکمیلی؛ این بیمه هزینه‌های درمانی فراتر از پوشش بیمه‌های پایه را پوشش می‌دهد.','تعریف نوع تکمیلی جدا و مستقیم است و پوشش کامل همه خسارت ادعا نشده است.')]],repair=r)
    b['audit']['error_categories']=['general versus supplementary insurance'];b['repair']['reason_fa']='سؤال عام با فقط بیمه تکمیلی پاسخ داده شده بود؛ گروه بیمه درمانی در چارچوب متن جدا از شرح تکمیلی افزوده شد.';b['repair']['recheck_reason_fa']='گروه عام با اول و نوع تکمیلی با صفر دوباره بررسی و اجتماعی بودن بیمه پایه انکار نشد.'
    c=decision(663,'تمام ده شاهد خوانده شد. صفر در حالت قرارداد در بنگاه، تنظیم سه نسخه و تحویل یک نسخه به خریدار را مستقیم می‌گوید. پاسخ طبق متن است و ادعای کفایت بنگاه برای پیش‌فروش یا تأیید قوانین جاری ندارد. اول و صفر دفتر اسناد رسمی و کنترل سند را ترجیح می‌دهند و سایر شواهد درباره ریسک سند و جعل و بند قراردادند؛ تعداد نسخه یا تحویل نسخه را نقض نمی‌کنند.',[[(0,'هنگام انجام قرارداد در بنگاه معاملات املاک، بنگاه باید قرارداد را در سه نسخه تنظیم کند و یک نسخه را به شما بدهد.','شرط انعقاد در بنگاه و تعداد نسخه و حق دریافت یک نسخه همگی مستقیم‌اند.')]])
    return [a,b,c]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==876
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0040';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[661,662,663],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0040/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=83,total_reviewed=879,remaining=270,next_position=664)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_661_663_v1',[661,662,663],'KEEP661 و663 و REPAIRED662؛ ادامه664.',cp['created_utc'])
