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
    a=decision(377,'تمام ده شاهد خوانده شد. صفر مدیریت درست پول برای رسیدن به آزادی و امنیت مالی را تعریف کوتاه سواد مالی می‌گوید. پاسخ معرفی شده است را حفظ می‌کند، نه تضمین حصول برای هر فرد. اول و دوم آزادی را مهم‌ترین نتیجه و سوم افقی دشوار می‌گویند؛ پاسخ از نتایج با آنها ناسازگار نیست. آزادی در چهارم و پنجم رهایی از سلطه پول است، نه صرف ثروتمند شدن؛ پاسخ معنای دیگری اضافه نکرده است.',[[(0,'سواد مالی یعنی مدیریت پول؛ یعنی پول‌هامون رو درست مدیریت بکنیم تا به آزادی و امنیت مالی برسیم.','هر دو هدف و ارتباط با مدیریت درست پول مستقیم آمده‌اند.')]])
    answer=rows(ROOT/'outputs.jsonl')[377]['response']['answer_text']
    reason='تمام ده شاهد خوانده شد. برنامه در سؤال نام یا زمینه ندارد. صفر برنامه آموزشی کشورها، اول و چهارم برنامه عملیاتی، دوم حمایت بهزیستی، سوم و هشتم آموزش زنان، ششم برنامه نگاه دینی، هفتم برنامه شخصی و نهم چهلستون را توضیح می‌دهند. اهداف چند برنامه در شواهد موجود است، اما انتخاب یکی بدون مرجع سؤال مجاز نیست. پاسخ فقط ابهام برنامه موردنظر را اعلام می‌کند.'
    b=decision(378,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)])
    b['audit']['status']='VALID_ABSTENTION';b['support']['abstention_review']='JUSTIFIED';b['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==858
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0030';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[377,378],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0030/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=64,total_reviewed=860,remaining=289,next_position=379)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_377_378_v1',[377,378],'KEEP377 و VALID_ABSTENTION378؛ ادامه379.',cp['created_utc'])
