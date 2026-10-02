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
    a=decision(719,'تمام ده شاهد خوانده شد. صفر پس از شناخت نیاز و خواسته و منابع و اصل مقایسه، واگذاری بخشی از تحلیل به ابزار یا متخصص را می‌گوید. اول ساده‌سازی و چهارم ابزار مقایسه و ششم تحلیل حرفه‌ای را تأیید می‌کنند. پاسخ مرحله پیچیده مقایسه را واگذار می‌کند نه فهم هدف و نه همه مسئولیت تصمیم را.',[[(0,'اول فرد باید اصلاً بداند نیاز و خواسته‌اش چیست، بداند آیا توان خرید دارد و بفهمد مقایسه‌کردن مفید است. بعد ممکن است ابزار فناوری مرحله پیچیده مقایسه را برایش انجام بدهد.','شناخت پیش‌نیاز و مرحله پیچیده مقایسه مستقیم است.'),(0,'دقیقاً. شخص اول باید به این مرحله برسد که بفهمد این خرید نیاز است یا خواسته، منابعش را مدیریت کند و اصل مقایسه را بپذیرد؛ بعد می‌تواند بخشی از تحلیل را به ابزار یا متخصص بسپارد.','گزینه متخصص و ابزار مستقیم است.')]])
    b=decision(720,'تمام ده شاهد خوانده شد. صفر صریحاً شروع کسب‌وکار و ورود به بازار را برای بازخورد واقعی و شنیدن صدای مشتری نیاز و مخالفت مطرح می‌کند. اول اقدام کوچک و عرضه محصول و چهارم شنیدن مشتری ناراضی را تأیید می‌کنند. سایر شواهد درباره مهارت کار و پیشنهاد شغلی و مدیریت مالیند و مانع این برداشت محدود نیستند.',[[(0,'این اطلاعات با نشستن به دست نمیاد. باید وارد بازار بشی و کسب‌وکار رو شروع کنی تا بازخورد واقعی بگیری.','شروع بازار برای بازخورد مستقیم است.'),(0,'دقیقاً این به ذهن من رسید. تا شروع نکنیم صدای مشتری، مخالفتش و نیازش رو نمی‌شنویم و چیزی برای اصلاح نداریم.','صدای مشتری مخالفت و نیاز مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==934
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0068';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[719,720],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0068/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=140,total_reviewed=936,remaining=213,next_position=721)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_719_720_v1',[719,720],'دو KEEP719 و720؛ ادامه721.',cp['created_utc'])
