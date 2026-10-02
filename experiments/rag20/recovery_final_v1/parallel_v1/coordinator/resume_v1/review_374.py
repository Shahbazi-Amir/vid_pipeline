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
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[373]['response'])
    r['answer_text']='در متن، مالیات بر درآمد املاک شامل درآمد ملک مانند اجاره است؛ مالیات نقل‌وانتقال ملک و حق واگذاری یا سرقفلی واحد تجاری هم جدا توضیح داده شده‌اند. این شرح متن است، نه تأیید مقررات فعلی.'
    r['claims'][0]['claim_text']=r['answer_text']
    data=__import__('json').loads(rows(ROOT/'inputs.jsonl')[373]['messages'][1]['content'])
    r['claims'][0]['evidence_ids']=[data['evidence'][i]['evidence_id'] for i in [0,8]]
    d=decision(374,'تمام ده شاهد خوانده شد. پاسخ اولیه مالیات املاک را به درآمد اجاره محدود می‌کرد در حالی که صفر نقل‌وانتقال و هشتم حق واگذاری یا سرقفلی را نیز جدا توضیح می‌دهند. پاسخ به مالیات بر درآمد املاک مقید و دیگر انواع شرح‌شده افزوده شدند. دوم درباره دارایی و خانه خالی نیز صحبت می‌کند اما وضعیت تاریخی اجرا روشن است؛ پاسخ مقررات جاری یا نرخ‌ها را تأیید نمی‌کند. مالیات حقوق، مشاغل، ارث و درآمد اتفاقی پایه‌های مستقل‌اند.',[[(0,'یکی املاک، درآمدی که ما از املاک داریم','درآمد ملک، و در ادامه همین شاهد مثال اجاره، عنوان مالیات بر درآمد املاک را روشن می‌کند.'),(0,'یه جایی هم هست که مالیات در واقع نقل‌وانتقال ملک می‌گیرن.','نقل‌وانتقال نوع دیگری از مالیات مربوط به ملک است و حذف آن از پاسخ سؤال کلی اصلاح شد.'),(8,'در اصطلاح می‌گن حق واگذاری یا سرقفلی که اگر حق تجاری اون واحد رو داری واگذار می‌کنی','واگذاری حق تجاری یا سرقفلی نیز صریحاً در بحث مالیات املاک آمده است.')]],repair=r)
    d['audit']['error_categories']=['incomplete scope','income tax versus property related taxes']
    d['repair']['reason_fa']='پاسخ فقط اجاره را می‌گفت؛ عنوان درآمد املاک دقیق و نقل‌وانتقال و سرقفلی شرح‌شده در متن افزوده شد.'
    d['repair']['recheck_reason_fa']='سه بخش پاسخ با صفر و هشتم دوباره تطبیق شدند؛ از ادعای نرخ و اجرای جاری خودداری و تاریخی بودن شرح صریح شد.'
    return [d]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==855
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0028';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[374],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0028/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=60,total_reviewed=856,remaining=293,next_position=375)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_374_v1',[374],'REPAIRED374؛ ادامه375.',cp['created_utc'])
