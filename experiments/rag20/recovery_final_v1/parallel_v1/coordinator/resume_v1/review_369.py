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
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[368]['response'])
    r['answer_text']='مدیریت هزینه متناسب با کاهش درآمد اهمیت دارد؛ اگر مستمری کفاف همه هزینه‌ها را نمی‌دهد، باید آن را پایه درآمد دانست و برای منابع مکمل برنامه داشت.'
    r['claims'][0]['claim_text']=r['answer_text']
    d=decision(369,'تمام ده شاهد خوانده شد. پاسخ اولیه شرط ناکافی بودن مستمری را حذف می‌کرد و پایه درآمد دانستن آن را بی‌قید ضروری می‌خواند. شرط صفر بازگردانده شد و الزام همه افراد به یک الگوی تأمین مالی حذف شد. مدیریت هزینه پس از کاهش درآمد در صفر و پنجم مستقیم است؛ برنامه منابع مکمل در اول، دوم و چهارم مطرح است. هفتم برابری درآمد سرمایه‌گذاری و شغل را هدف می‌گوید ولی پاسخ آن را شرط همگانی نکرده است. بیمه، سلامت، هویت و زمان توصیه‌های مکمل‌اند.',[[(0,'اگر مستمری فعلی کفاف همه هزینه‌ها را نمی‌دهد، باید آن را یک «پایه درآمد» بدانیم، نه تمام برنامه مالی.','قید ناکافی بودن مستمری و نیاز به برنامه فراتر از مستمری مستقیم است.'),(0,'یکی از مهم‌ترین بخش‌ها مدیریت سبک خرج‌کردن است. فرد نمی‌تواند بعد از کاهش درآمد دقیقاً همان الگوی هزینه دوره اشتغال را ادامه بدهد و انتظار داشته باشد تعادل حفظ شود.','تناسب مدیریت خرج با کاهش درآمد صریح است.')]],repair=r)
    d['audit']['error_categories']=['omitted condition']
    d['repair']['reason_fa']='شرط ناکافی بودن مستمری برای پایه درآمد دانستن آن در پاسخ حذف شده بود؛ شرط بازگردانده شد.'
    d['repair']['recheck_reason_fa']='پاسخ و claim فعال با دو عبارت صفر و شواهد مکمل برنامه منابع دیگر دوباره تطبیق شدند.'
    return [d]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==850
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0025';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[369],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0025/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=55,total_reviewed=851,remaining=298,next_position=370)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_369_v1',[369],'REPAIRED369؛ ادامه370.',cp['created_utc'])
