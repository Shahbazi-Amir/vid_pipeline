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
    data=json.loads(rows(ROOT/'inputs.jsonl')[663]['messages'][1]['content'])
    factual='اگر منظور دورهٔ بازپرداخت بدهی است، متن نمونه‌های یک‌ساله، دوساله و حتی ده‌ساله را بیان می‌کند؛'
    limit=' نوع پرداخت در سؤال مشخص نشده است.'
    r=dict(answer_text=factual+limit,claims=[dict(claim_text=factual,claim_type='FACTUAL',evidence_ids=[data['evidence'][3]['evidence_id']])])
    a=decision(664,'تمام ده شاهد خوانده شد. امتناع اولیه صرفاً صفر و انتظار صندوق خانوادگی را معرفی می‌کرد، اما اول و سوم دوره پرداخت بدهی را یک و دو و حتی ده سال می‌گویند. سؤال نوع پرداخت را روشن نکرده و دوره سپرده و امنیت مالی و دریافت صندوق مفاهیم دیگرند. پاسخ با اگر منظور بازپرداخت بدهی است مقید شد و ابهام سؤال صریح باقی ماند؛ سال‌ها مثال‌اند نه سقف قانونی یا حد عمومی همه بدهی‌ها.',[[(3,'عامل بعدی طول دوره بازپرداخت است. یک بدهی ممکن است یک‌ساله، دوساله یا حتی ده‌ساله باشد.','هر سه مثال و عنوان دوره بازپرداخت بدهی مستقیم‌اند؛ پاسخ شرطی هیچ نوع پرداخت نامعلوم را قطعی انتخاب نمی‌کند.')]],repair=r,units=[dict(text=factual,kind='FACTUAL',claim_indices=[0],reason_fa='پاسخ شرطی درباره بازپرداخت بدهی با سوم پوشش دارد.'),dict(text=limit,kind='EVIDENCE_LIMITATION',claim_indices=[],reason_fa='نوع پرداخت سؤال معین نیست و شواهد چند مفهوم متفاوت دارند.')])
    a['audit']['error_categories']=['incomplete evidence review','unresolved payment reference'];a['repair']['reason_fa']='شواهد بازپرداخت بدهی نادیده مانده و همه قطعات به صندوق نسبت داده شده بودند؛ پاسخ شرطی مستند همراه ابهام جایگزین شد.';a['repair']['recheck_reason_fa']='سه مدت با سوم تطبیق و عبارت ابهام از claim factual جدا ثبت شد.'
    data=json.loads(rows(ROOT/'inputs.jsonl')[664]['messages'][1]['content'])
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[664]['response'])
    r['answer_text']='در توضیح متن، اگر اعتبار صرفاً مصرف را افزایش دهد و تولید یا ظرفیت تازه‌ای در بخش واقعی ایجاد نشود، افزایش تقاضا و نقدینگی می‌تواند فشار تورمی و کاهش ارزش پول ایجاد کند.'
    r['claims'][0]['claim_text']=r['answer_text'];r['claims'][0]['evidence_ids']=[data['evidence'][i]['evidence_id'] for i in [0,2]]
    b=decision(665,'تمام ده شاهد خوانده شد. صفر اثر تورمی را در فرض خلق نشدن واقعیت اقتصادی شرح می‌دهد و دوم شرط مصرف اضافه بدون ظرفیت تازه و می‌تواند را دقیق می‌گوید. پاسخ قبلی اعتبار مصرفی را بی‌شرط علت قطعی می‌دانست؛ شرط و احتمال بازگردانده شدند. اول و پنجم خلاصه قطعی‌ترند اما پاسخ با فرض مشترک و روایت متن محدود است؛ قواعد بدهی فردی، درصد و وام خوب به اثر کلان منتقل نشدند.',[[(2,'اگر اعتبار و تسهیلات صرفاً به مصرف اضافه تبدیل شود، بدون اینکه در بخش واقعی اقتصاد تولید یا ظرفیت تازه‌ای ایجاد شده باشد، حجم تقاضا و پول بالا می‌رود و می‌تواند فشار تورمی ایجاد کند.','شرط، تقاضا و پول و احتمال فشار تورمی کامل‌اند.'),(0,'و تورم ایجاد می‌شه و ارزش پول ملی کاهش پیدا می‌کنه','ارتباط کاهش ارزش پول با این سازوکار در توضیح متن مستقیم است.')]],repair=r)
    b['audit']['error_categories']=['omitted economic condition','overstated certainty'];b['repair']['reason_fa']='شرط خلق نشدن تولید و ظرفیت واقعی حذف شده بود؛ شرط و امکان اثر تورمی بازگردانده شد.';b['repair']['recheck_reason_fa']='پاسخ فعال با شرط دوم و سازوکار و کاهش ارزش صفر دوباره بررسی شد.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==879
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0041';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[664,665],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0041/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=85,total_reviewed=881,remaining=268,next_position=666)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_664_665_v1',[664,665],'دو REPAIRED664 و665؛ ادامه666.',cp['created_utc'])
