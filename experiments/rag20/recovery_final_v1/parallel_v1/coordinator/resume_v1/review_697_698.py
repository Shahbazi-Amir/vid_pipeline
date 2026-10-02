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
    a=decision(697,'تمام ده شاهد خوانده شد. صفر دنبال کردن کار دوست‌داشتنی منطبق با علاقه و استعداد را راه موفقیت و لذت می‌داند و داستان رسیدن به خواسته و تبدیل زحمت به لذت را بیان می‌کند. پاسخ به متن نسبت داده و راهی می‌گوید، نه تضمین ثروت یا حذف همه سختی‌ها؛ اول کارهای نامحبوب در مسیر علاقه و هفتم آزمودن شغل مکمل‌اند.',[[(0,'پس برای پیدا کردن موفقیت و لذت در زندگی باید به دنبال کاری باشیم که آن را دوست داریم؛','راه موفقیت و لذت و علاقه به کار مستقیم‌اند.')]])
    b=decision(698,'تمام ده شاهد خوانده شد. صفر هلند هفتاد و انگلستان سی درصد کارمندان را برای ناآگاهی از درآمد بازنشستگی می‌گوید. پاسخ طبق پیمایش مقید و ترتیب کشورها درست است؛ چهارم امنیت عمومی شمال اروپا تناقض با ندانستن مبلغ دقیق نیست. اعداد آمریکا و سواد مالی و خطای درآمد پاره‌وقت جامعه و سنجه متفاوت‌اند.',[[(0,'پیمایش‌ها نشان می‌دهد 70 درصد کارمندان در هلند، نمی‌دانند درآمد بازنشستگی آن‌ها چقدر خواهد بود. در انگلستان نیز این عدد به 30 درصد می‌رسد.','جامعه و دو کشور و دو درصد مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==912
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0057';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[697,698],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0057/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=118,total_reviewed=914,remaining=235,next_position=699)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_697_698_v1',[697,698],'دو KEEP697 و698؛ ادامه699.',cp['created_utc'])
