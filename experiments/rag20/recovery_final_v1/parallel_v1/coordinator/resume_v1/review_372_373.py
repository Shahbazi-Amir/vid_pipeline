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
    a=decision(372,'تمام ده شاهد خوانده شد. صفر، اول، سوم و چهارم سواد مالی را مجموعه دانش، مهارت، گرایش و رفتار برای مدیریت درست مالی تعریف می‌کنند و هفتم دانایی و نگرش و رفتار و مهارت را باز می‌کند. پاسخ تعریف کوتاه بدون تضمین ثروت یا مصونیت از بحران است؛ رشد اقتصاد، سرفصل‌ها و اهمیت کودک جزئیات مکمل تعریف‌اند. تفاوت تعداد سرفصل‌های ششم در پاسخ نیامده است.',[[(0,'سواد مالی مجموعه‌ای از دانش‌ها، مهارت‌ها، گرایش‌ها و رفتارهای مالی است که از یک سو به افراد کمک می‌کند سررشتۀ امور مالی‌شان را در دست بگیرند','چهار جزء و مدیریت امور مالی تعریف پاسخ را پشتیبانی می‌کنند.')]])
    b=decision(373,'تمام ده شاهد خوانده شد. صفر با همان شرط تعیین و بررسی انتظارات، یافتن سبک را ساده‌تر می‌داند. سؤال شرط را صریح دارد و پاسخ نتیجه همان فرض است، نه تضمین یافتن شغل یا برتری یک سبک برای همه. سایر شواهد ویژگی و ارزش‌آفرینی و تجربه سبک‌ها را توضیح می‌دهند؛ خانه اجاره‌ای موضوع متفاوت است.',[[(0,'اگر انتظارات شغلی‌مان را مشخص و بررسی کرده باشیم، یافتن سبک مناسب، ساده‌تر خواهد بود.','شرط سؤال و نتیجه مقایسه‌ای ساده‌تر عیناً در شاهد آمده‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==853
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0027';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[372,373],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0027/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=59,total_reviewed=855,remaining=294,next_position=374)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_372_373_v1',[372,373],'دو KEEP372 و373؛ ادامه374.',cp['created_utc'])
