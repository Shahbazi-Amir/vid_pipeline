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
    answer=rows(ROOT/'outputs.jsonl')[665]['response']['answer_text'];reason='تمام ده شاهد خوانده شد. روش‌های ناانصاف در سؤال تعریف یا مرجع مشخصی ندارد. صفر کلاهبرداری و مراقبت از اجرای تصمیم، پنجم نگرش نادرست، سوم طراحی اپلیکیشن، ششم و هفتم سخت‌گیری بودجه و هشتم نیاز و خواسته را توضیح می‌دهند. هیچ روش مشخص با همین نام به یک اثر معین وصل نشده؛ امتناع از تعیین اثر آن روش نامعلوم موجه است و نبود همه اطلاعات تصمیم مالی ادعا نمی‌شود.'
    a=decision(666,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)]);a['audit']['status']='VALID_ABSTENTION';a['support']['abstention_review']='JUSTIFIED';a['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    data=json.loads(rows(ROOT/'inputs.jsonl')[666]['messages'][1]['content']);answer='در متن، از حساب‌های بانکی متعدد در بانک‌های مختلف صحبت شده است؛ از جمله بانک‌هایی که محل کار برای واریز حقوق معرفی می‌کند.'
    r=dict(answer_text=answer,claims=[dict(claim_text=answer,claim_type='FACTUAL',evidence_ids=[data['evidence'][i]['evidence_id'] for i in [1,2]])])
    b=decision(667,'تمام ده شاهد خوانده شد. اول حساب‌های متعدد بانکی را می‌گوید و دوم تغییر محل کار و معرفی بانک‌های مختلف را مثال می‌زند. سؤال جاهای حساب را می‌پرسد و پاسخ می‌تواند در همین سطح کلی و مقید به متن بانک‌ها را معرفی کند؛ لازم نیست نام بانک یا حساب واقعی کاربر حدس زده شود. امتناع اولیه کلی‌تر از لازم بود؛ انواع قرض‌الحسنه و سپرده و سرد و گرم دسته‌بندی حساب‌اند، نه مکان‌های جدید و با مکان خلط نشدند.',[[(1,'این روزها هر کدام از ما حساب‌های متعدد بانکی داریم','محل کلی حساب‌ها بانک است و تعدد حساب‌ها صریح است.'),(2,'تو ایران ما هر جا می‌ریم کار کنیم، یک بانکی رو معرفی می‌کنیم. یعنی ما اگه ده جا مثلاً کار تغییر داده باشیم، ده تا بانک هم در واقع حساب داریم.','بانک‌های متعدد معرفی‌شده در محل کار مثال متن‌اند؛ تعداد ده و هویت کاربر تعمیم نشده است.')]],repair=r)
    b['audit']['error_categories']=['overbroad abstention'];b['repair']['reason_fa']='شواهد مکان کلی حساب‌ها را بانک‌های متعدد می‌گویند؛ پاسخ محدود به روایت متن جای امتناع کامل نشست.';b['repair']['recheck_reason_fa']='تعدد بانکی با اول و مثال محل کار با دوم بررسی و نام بانک یا وضع واقعی کاربر اضافه نشد.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==881
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0042';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[666,667],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0042/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=87,total_reviewed=883,remaining=266,next_position=668)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_666_667_v1',[666,667],'VALID_ABSTENTION666 و REPAIRED667؛ ادامه668.',cp['created_utc'])
