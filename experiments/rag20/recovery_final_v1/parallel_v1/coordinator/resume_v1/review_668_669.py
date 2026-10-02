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
    a=decision(668,'تمام ده شاهد خوانده شد. صفر چهار مزیت پاسخ را تأمین مالی با خردسرمایه، شفافیت، نقدشوندگی و سرمایه اندک می‌گوید. دوم تفاوت نقدشوندگی نسبت به ملک را در بسیاری شرایط و لزوم مدیریت ریسک توضیح می‌دهد؛ پاسخ ویژگی نقدشوندگی می‌گوید نه تضمین فروش فوری هر سهم. سایر شواهد ریسک و ترکیب دارایی و مسیر صندوق دارند؛ توصیه ورود همه افراد یا تضمین سود افزوده نشده است.',[[(0,'تولید داخلی و رشد اقتصادی: جمع‌آوری سرمایه‌های اندک و تأمین مالی شرکت‌ها.','تأمین مالی با سرمایه خرد مستقیم است.'),(0,'شفافیت اطلاعاتی: بازرسی و در دسترس بودن اطلاعات شرکت‌ها از طریق سامانه کدال.','شفافیت اطلاعات مستقیم است.'),(0,'نقدشوندگی: قابلیت تبدیل بخش یا کل سرمایه به وجه نقد در مدت زمانی کوتاه.','مزیت نقدشوندگی مستقیم است، نه تضمین همگانی فروش فوری.'),(0,'سرمایه‌ اندک: قابل خریداری بودن هر سهم یا واحد صندوق سرمایه‌گذاری به سادگی.','ورود با سرمایه اندک در فهرست مزایا صریح است.')]])
    b=decision(669,'تمام ده شاهد خوانده شد. صفر محدودیت آگاهانه و خودانتخاب بر اساس ارزش و اولویت را بخشی از کار بودجه برای مدیریت بهتر منابع می‌داند. پاسخ آگاهانه را حفظ کرده و محدودیت تحمیلی یا خساست یا حذف تمام تفریح نمی‌گوید. اول و دوم برنامه کنترل ورود و خروج، پنجم بازنگری و ششم تخصیص به مهم‌ترین‌ها، و هفتم صندوق‌ها اجزای دیگرند؛ تنها وظیفه بودجه ادعا نشده است.',[[(0,'اتفاقاً بخشی از کار بودجه این است که انتخاب‌های ما را آگاهانه محدود کند؛ محدودیتی که خودمان بر اساس ارزش‌ها و اولویت‌ها تعیین کرده‌ایم. همین محدودیتِ انتخاب‌شده کمک می‌کند منابعمان را بهتر مدیریت کنیم','بخشی از کار، آگاهی و خودانتخاب و هدف مدیریت منابع همه مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==883
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0043';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[668,669],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0043/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=89,total_reviewed=885,remaining=264,next_position=670)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_668_669_v1',[668,669],'دو KEEP668 و669؛ ادامه670.',cp['created_utc'])
