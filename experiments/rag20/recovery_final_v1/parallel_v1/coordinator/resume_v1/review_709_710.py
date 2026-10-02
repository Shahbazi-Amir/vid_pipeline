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
    a=decision(709,'تمام ده شاهد خوانده شد. صفر جریان پول را از افزایش ارزش بازار جدا می‌کند و هزینه تعمیر و نگهداری منزل مسکونی را مثال می‌زند. اول و دوم تعریف خروج پول، ششم مصرف شخصی در برابر کار اقتصادی و هشتم مثال خودرو را تأیید می‌کنند. چهارم تعریف قدیمی درآمدزا را با افزایش ارزش مخلوط می‌کند اما پاسخ مطابق تفکیک صریح صفر است.',[[(0,'مثلاً خونه‌ای که خودمون توش زندگی می‌کنیم، از نظر جریان پولی معمولاً هزینه‌زاست؛ تعمیر، نگهداری، شارژ و هزینه‌های مختلف داره. ممکنه ارزش بازارش زیاد بشه، ولی تا وقتی برای ما جریان پول ایجاد نمی‌کنه، در این بحث «درآمدزا» نیست.','هم هزینه نگهداری و هم ناکافی بودن افزایش قیمت مستقیم بیان شده است.')]])
    b=decision(710,'تمام ده شاهد خوانده شد. صفر منابع دینی مورد اشاره و میانه‌روی و تدبیر معیشت و تفاوت انفاق و ولخرجی را صریح بیان می‌کند. سوم تدبیر مالی را تأیید می‌کند. سایر شواهد منابع تولید، سرمایه و کودک معنای دیگر منابع هستند و مرجع منابع دینی را تغییر نمی‌دهند؛ پاسخ به منابع مورد اشاره محدود مانده است.',[[(0,'نه. اینجا باید مفهوم «تدبیر معیشت» را حفظ کنیم. ولخرجی با انفاق یکی نیست. در همان منابع، میانه‌روی و تدبیر هم مورد تأکید قرار گرفته است.','تمام ادعای پاسخ مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==924
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0063';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[709,710],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0063/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=130,total_reviewed=926,remaining=223,next_position=711)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_709_710_v1',[709,710],'دو KEEP709 و710؛ ادامه711.',cp['created_utc'])
