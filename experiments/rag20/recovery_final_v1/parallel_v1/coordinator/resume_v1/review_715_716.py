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
    a=decision(715,'تمام ده شاهد خوانده شد. صفر هفت مهارت را نام می‌برد و انجام آزمون در همین قسمت عصر شیرین را صریح گزارش می‌کند. اول ارزیابی سود و زیان و چهارم تأمین مالی و ششم هویت کسب‌وکار موضوع قسمت‌های دیگرند. پاسخ انجام آزمون هفت مهارت را از آزمون سود یا دوره دیگر جدا نگه داشته است.',[[(0,'بر اساس آموزه‌های سواد مالی، خانم‌های که قصد راه‌اندازی کسب‌وکار خانگی را دارند باید هفت مهارت مهم راهبردی، ریسک‌پذیری، تأثیرگذاری، مربیگری، توسعۀ تیم، هوش هیجانی و مهارت‌های کارآفرینی را در خود ارزیابی کنند.','عدد هفت و موضوع مهارت‌ها روشن است.'),(0,'در این قسمت از برنامۀ عصر شیرین، آزمون اندازه‌گیری این مهارت‌ها را انجام دادیم و به تفصیل دربارۀ هر کدام صحبت کردیم.','انجام آزمون در برنامه صریح است.')]])
    b=decision(716,'تمام ده شاهد خوانده شد. صفر کار داوطلبانه را قدم اول پیدا کردن شغل معرفی می‌کند. دوم سنجش علاقه و تقویت رزومه و ارتباط شغلی، ششم راه‌های ورود به کار، هشتم یافتن شغل و نهم تجربه را توضیح می‌دهند. پاسخ معرفی آموزشی این ویژگی است، نه تضمین استخدام یا شرط اجباری همه شغل‌ها.',[[(0,'کار داوطلبانه، قدم اول برای پیدا کردن شغل بود.','معرفی قدم اول مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==930
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0066';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[715,716],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0066/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=136,total_reviewed=932,remaining=217,next_position=717)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_715_716_v1',[715,716],'دو KEEP715 و716؛ ادامه717.',cp['created_utc'])
