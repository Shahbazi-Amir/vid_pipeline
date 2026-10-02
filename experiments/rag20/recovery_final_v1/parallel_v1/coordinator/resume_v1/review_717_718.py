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
    a=decision(717,'تمام ده شاهد خوانده شد. صفر برای نزدیک شدن کودک به شغل مناسب کار داوطلبانه را همراه تابستانه و منزل معرفی می‌کند. سوم پنجم هفتم و نهم مزایای تجربه واقعی و مسیر شغل را تأیید می‌کنند. سؤال عمومی است اما پاسخ یکی از روش‌های مطرح‌شده می‌گوید و انحصار روش یا تضمین استخدام ندارد.',[[(0,'یکی از مهم‌ترین کارها، کار داوطلبانه، کار تابستانه و کار در منزل است تا فرزند تجربه کار کردن داشته باشد.','روش تجربه کار برای رسیدن به شغل مناسب در مقدمه قطعه معرفی می‌شود.')]])
    answer=rows(ROOT/'outputs.jsonl')[717]['response']['answer_text'];reason='تمام ده شاهد خوانده شد. مرجع این اصل در سؤال معلوم نیست. اول اصل ارزش‌آفرینی پیش از داشتن، دوم آموزش و احساس، چهارم اصل لازم بودن قرارداد، پنجم تفاوت فقر و غنای عصرها و هشتم قانون عرضه و تقاضا را مطرح می‌کنند. هیچ قرینه یکتای تعیین اصل سؤال نیست و انتخاب یکی حدس خواهد بود. خودداری پاسخ موجه است.'
    b=decision(718,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)]);b['audit']['status']='VALID_ABSTENTION';b['support']['abstention_review']='JUSTIFIED';b['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==932
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0067';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[717,718],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0067/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=138,total_reviewed=934,remaining=215,next_position=719)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_717_718_v1',[717,718],'KEEP717 و VALID_ABSTENTION718؛ ادامه719.',cp['created_utc'])
