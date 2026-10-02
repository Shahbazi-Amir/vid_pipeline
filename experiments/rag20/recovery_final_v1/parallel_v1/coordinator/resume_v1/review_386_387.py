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
    a=decision(386,'تمام ده شاهد خوانده شد. صفر به صراحت در شرایط تورمی بالاتر بودن قیمت فروش از قیمت مصرف‌کننده تاریخی را لزوماً اجحاف نمی‌داند و تاریخ تولید را معیار قیمت درج‌شده توضیح می‌دهد. پاسخ متن می‌گوید و لزوماً را حفظ می‌کند و حکم قانونی مجاز بودن فروش یا نفی تمام اجحاف‌ها نیست. نهم مثال حفظ موجودی و تفاوت سود واقعی و اسمی را دارد؛ سایر شواهد تورم و قیمت تعادلی و افت کیفیت زندگی با گزارشی بودن پاسخ ناسازگار نیستند.',[[(0,'در واقع با معیار تومن اون تاریخ تولید بوده، که ممکنه حالا واقعاً تغییر بکنه، تغییر کرده باشه. بنابراین توی در واقع شرایط تورمی، وقتی که قیمت‌ها رو فروشگاه‌ها بیشتر از قیمت مصرف‌کننده می‌دن، لزوماً اجحاف نمی‌کنن.','تاریخ تولید و شرایط تورمی و نفی الزام اجحاف هر سه مستقیم‌اند؛ پاسخ فقط نظر متن را گزارش می‌کند.')]])
    b=decision(387,'تمام ده شاهد خوانده شد. صفر و اول و سوم و چهارم مجموعه دانش و مهارت و گرایش و رفتار برای مدیریت مالی را می‌گویند؛ هفتم دانایی و خواستن و توانستن را توضیح می‌دهد. پاسخ تعریف کوتاه است، نه تضمین پولدار شدن یا حذف بحران و نه ادعای یگانگی تعریف در ششم. سرفصل‌ها و مزایای آموزش کودکی جزئیات مکمل‌اند و حذف آنها تعریف پاسخ را بی‌پشتوانه نمی‌کند.',[[(0,'سواد مالی مجموعه‌ای از دانش‌ها، مهارت‌ها، گرایش‌ها و رفتارهای مالی است که از یک سو به افراد کمک می‌کند سررشتۀ امور مالی‌شان را در دست بگیرند','چهار جزء تعریف و مدیریت مالی مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==867
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0035';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[386,387],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0035/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=73,total_reviewed=869,remaining=280,next_position=388)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_386_387_v1',[386,387],'دو KEEP386 و387؛ ادامه388.',cp['created_utc'])
