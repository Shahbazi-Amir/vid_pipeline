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
    data=json.loads(rows(ROOT/'inputs.jsonl')[383]['messages'][1]['content'])
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[383]['response'])
    r['answer_text']='در فرایند برنامه‌ریزی مالی، گام نخست تعیین موقعیت مالی کنونی شامل درآمد، پس‌انداز، هزینه و بدهی است؛ در فرایند مدیریت هزینه‌ها، نخست ثبت هزینه‌ها برای سه ماه و بررسی خریدهای غیرضروری مطرح شده است.'
    r['claims'][0]['claim_text']=r['answer_text'];r['claims'][0]['evidence_ids']=[data['evidence'][i]['evidence_id'] for i in [0,9]]
    a=decision(384,'تمام ده شاهد خوانده شد. صفر گام نخست برنامه‌ریزی مالی را تعیین وضعیت می‌گوید اما اول، دوم، سوم و ششم شروع سرفصل‌ها و مدیریت خرج را بیان می‌کنند و نهم اولین گام فرایند مدیریت هزینه را ثبت سه‌ماهه می‌داند. پاسخ قبلی یک چارچوب را بی‌قید به کل مدیریت مالی نسبت می‌داد؛ اکنون دو فرایند با نام جدا آمده‌اند. پلکان توانمندی مالی در چهارم و هفتم مراحل وضعیت است و مرحله اقدام تلقی نشده است.',[[(0,'1. تعیین موقعیت مالی کنونی؛\nدر اولین گام، وضعیت فعلی درآمد، پس\u200cانداز، هزینه\u200cهای زندگی و بدهی خود را تعیین کنید.','عنوان و اجزای گام نخست برنامه‌ریزی مستقیم‌اند.'),(9,'اولین گام از فرایند مدیریت هزینه‌ها، نوشتن ‌آن‌ها به مدت سه ماه و بررسی خریدهای غیرضروری است.','گام نخست مدیریت هزینه‌ها با مدت و بررسی خرید غیرضروری مستقیم است.')]],repair=r)
    a['audit']['error_categories']=['unqualified framework'];a['repair']['reason_fa']='گام اول دو فرایند متفاوت در شواهد نام‌گذاری نشده بود؛ برنامه‌ریزی مالی از مدیریت هزینه جدا شد.';a['repair']['recheck_reason_fa']='هر دو بخش با صفر و نهم دوباره بررسی و با سرفصل‌ها و پلکان خلط نشدند.'
    data=json.loads(rows(ROOT/'inputs.jsonl')[384]['messages'][1]['content'])
    answer='برای آموزش سواد مالی به کودکان، از جمله از قصه، موسیقی و تصاویر، در قالب کتاب‌های صوتی و تصویری استفاده می‌شود.'
    r=dict(answer_text=answer,claims=[dict(claim_text=answer,claim_type='FACTUAL',evidence_ids=[data['evidence'][6]['evidence_id']])])
    b=decision(385,'تمام ده شاهد خوانده شد. ششم ابزارهای آموزش کودکان را صریحاً قصه و موسیقی و رنگ، و دو محمل صوتی و تصویری می‌گوید؛ پس امتناع اولیه ناموجه بود. پاسخ با کودکان و از جمله مقید شد چون هفتم نمایشگاه تعاملی و بازی و هشتم دوره درسی را هم دارد. پاسخ سن مشخص، اثربخشی تضمینی یا فراموش نشدن قطعی اضافه نکرده است.',[[(6,'کودکان با موسیقی، رنگ و قصه زود عجین می‌شوند و با کمک این ابزار می‌توان به آن‌ها آموزش داد.','قصه و موسیقی ابزار آموزشی کودکان در متن‌اند.'),(6,'بنابراین برای آموزش‌ آن‌ها خوب است از دو محمل استفاده کرد: کتاب‌های صوتی و کتاب‌های تصویری.','دو قالب نام‌برده مستقیم‌اند.'),(6,'سواد مالی را نیز می‌توان با کمک موسیقی و تصاویر زیبا آموزش داد تا اثربخش‌تر باشد.','کاربرد مشخص ابزارها برای سواد مالی صریح است.')]],repair=r)
    b['audit']['error_categories']=['unsupported abstention'];b['repair']['reason_fa']='ابزارهای صریح شاهد ششم نادیده مانده بود؛ پاسخ مستند برای کودکان جایگزین شد.';b['repair']['recheck_reason_fa']='تمام پاسخ و claim تازه با سه عبارت ششم تطبیق و ابزارهای دیگر انکار نشدند.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==865
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0034';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[384,385],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0034/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=71,total_reviewed=867,remaining=282,next_position=386)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_384_385_v1',[384,385],'دو REPAIRED384 و385؛ ادامه386.',cp['created_utc'])
