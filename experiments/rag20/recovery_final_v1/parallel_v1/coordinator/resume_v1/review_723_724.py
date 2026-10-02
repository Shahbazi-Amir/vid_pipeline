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
    data=json.loads(rows(ROOT/'inputs.jsonl')[722]['messages'][1]['content']);answer='در مثال متن، زندگی روزمره شامل کارهایی است که از بیدارشدن تا خوابیدن انجام می‌دهیم و زمان محدود روز را به آن‌ها اختصاص می‌دهیم.'
    r=dict(answer_text=answer,claims=[dict(claim_text=answer,claim_type='FACTUAL',evidence_ids=[data['evidence'][6]['evidence_id']])])
    a=decision(723,'تمام ده شاهد خوانده شد. ششم در مثال زندگی شخصی چرخه صبح بیدارشدن، انجام کارها و خوابیدن و تخصیص۲۴ ساعت به فعالیت‌های متفاوت را مستقیم شرح می‌دهد؛ هشتم رفتارهای عادی را مثال می‌زند. پاسخ قبلی نبود تعریف را بیش از حد سخت‌گیرانه گرفته بود؛ پاسخ با قید در مثال متن توصیف مستقیم ششم را ارائه می‌کند نه تعریف فلسفی خارج متن.',[[(6,'ما توی زندگی روزمره‌مون صبح از خواب بلند می‌شیم، یه سری کارها رو انجام می‌دیم و بعد مثلاً می‌ریم می‌خوابیم. هر کسی از ما هم ۲۴ ساعت داره و این ۲۴ ساعتش رو داره به کارهای متفاوتی تخصیص','فعالیت روزانه و اختصاص زمان محدود در مثال مستقیم است.')]],repair=r)
    a['audit']['error_categories']=['unnecessary abstention'];a['repair']['reason_fa']='شاهد ششم توصیف روشن زندگی روزمره دارد؛ پاسخ محدود به مثال متن جایگزین خودداری شد.';a['repair']['recheck_reason_fa']='پاسخ با توصیف فعالیت از صبح تا خواب و تخصیص زمان ششم تطبیق شد؛ تعریف جامع بیرونی اضافه نشد.'
    b=decision(724,'تمام ده شاهد خوانده شد. صفر بند۲ بررسی سند و قرارداد و اکتفا نکردن به بنگاه و بند۳ پیشنهاد وکیل را دارد. اول ادامه کنترل مالک رسمی و سوم و ششم بررسی سند و قرارداد را توضیح می‌دهند. پاسخ توصیه احتیاطی متن است و صحت معامله یا مالکیت و کفایت این سه اقدام را تضمین نمی‌کند.',[[(0,'2. هنگام بستن قرارداد پیش‌فروش ساختمان، سند و قرارداد فروش را کنترل کنید و صرفاً به اظهارات بنگاه معاملات املاک اعتماد نکنید.','بررسی سند و قرارداد و عدم اعتماد صرف مستقیم است.'),(0,'3. بهتر است به دلیل سنگین بودن رقم قرارداد، وکیلی همراه خود داشته باشید و تنها وارد این‌گونه معامله‌ها نشوید.','وکیل به صورت پیشنهاد است نه الزام.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==938
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0070';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[723,724],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0070/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=144,total_reviewed=940,remaining=209,next_position=725)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_723_724_v1',[723,724],'REPAIRED723 وKEEP724؛ ادامه725.',cp['created_utc'])
