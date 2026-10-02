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
    a=decision(685,'تمام ده شاهد خوانده شد. صفر حذف چهار صفر را تغییر اسمی می‌داند و واکنش رفتاری و اصطکاک کوتاه‌مدت را ممکن می‌گوید؛ دوم تقسیم همه اعداد و نبود تغییر واقعی مشخص را تأیید می‌کند. پاسخ احتمال و کوتاه‌مدت را حفظ کرده و برابری تغییر عددی با رشد قدرت خرید یا هیچ واکنشی نمی‌گوید. سایر شواهد ادراک و خبر و خرید موضوعات جدا هستند.',[[(0,'این تحول توی قسمت اسمیه، توی اون دنیای عددیه.','تغییر اسمی مستقیم است.'),(0,'هیچ اتفاق مشخصی نمی‌افته. ممکنه حالا تغییر رفتار آدم‌ها یا واکنش‌های رفتاری که به این دادن، یک کمی اصطکاک‌ها و یه سری تغییرات کوتاه‌مدتی داشته باشه، ولی در بلندمدت نه.','نبود تغییر واقعی مشخص و امکان واکنش کوتاه‌مدت مستقیم‌اند.')]])
    b=decision(686,'تمام ده شاهد خوانده شد. صفر نیاز را با آزار نبود آن تعریف می‌کند و آب را مثال مستقیم می‌آورد؛ دوم نارضایتی نبود آب و سوم دشوار شدن زندگی و چهارم نیاز بودن آب تأیید می‌کنند. پاسخ اثر نبود آب در مثال نیاز است؛ نبود آب کشاورزی زمین یا آلودگی آب ششم به آن اضافه نشده است.',[[(0,'چیزی که بودنش شاید تفاوت بزرگی در زندگی ما ایجاد نکند، اما نبودنش ما را واقعاً اذیت کند، «نیاز» است. مثلاً وقتی سر سفره آب هست، ممکن است حضورش خیلی به چشم نیاید؛ اما اگر آب نباشد فوراً می‌پرسیم «آب کو؟» این نشان می‌دهد آب یک نیاز است.','اثر آزار نبود و مثال آب و نیاز مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==900
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0051';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[685,686],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0051/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=106,total_reviewed=902,remaining=247,next_position=687)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_685_686_v1',[685,686],'دو KEEP685 و686؛ ادامه687.',cp['created_utc'])
