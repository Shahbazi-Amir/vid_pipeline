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
    a=decision(699,'تمام ده شاهد خوانده شد. دوم در نقد فیلم بیرو دنیای تحقق رؤیا را پر از ناملایمات و محدودیت و ظلم می‌نامد؛ پاسخ در توصیف متن مقید است و حکم عام فلسفی یا ادعای همه ویژگی‌های جهان نمی‌سازد. ششم و نهم واقعی در برابر اسمی و اول بعد جسمی بافت متفاوت‌اند، با این توصیف ادبی خلط نشده‌اند.',[[(2,'دنیایی که پر است از ناملایمات، محدودیت‌ها، ظلم‌ها و بی‌انصافی‌ها.','سه ویژگی پاسخ در توصیف متن مستقیم‌اند.')]])
    b=decision(700,'تمام ده شاهد خوانده شد. با وجود نویسه خراب در سؤال، منظور شرط سنگین شدن ثروت بر حرکت روشن است. صفر دلبستگی و دشواری دل بریدن و سفر زندگی را بیان می‌کند و تأکید می‌کند خود ثروت مانع عاقبت بخیری نیست؛ پاسخ شرط را حفظ کرده و همه ثروتمندان یا فقر را ضامن رستگاری نمی‌داند. پنجم دلبستگی مکمل و سایر شواهد خلق ثروت و تصمیم موضوعات جدا هستند.',[[(0,'با وجود این همه دلبستگی، مردن و دل بریدن برایش دشوار خواهد شد.','دشواری دل بریدن ناشی از دلبستگی مستقیم است.'),(0,'ثروت و توانگری، اگر دلبستگی آورد و وزنه سنگینی بر پای حرکت شود، سفر زندگی به دشواری طی خواهد شد.','شرط دلبستگی و دشواری سفر زندگی مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==914
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0058';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[699,700],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0058/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=120,total_reviewed=916,remaining=233,next_position=701)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_699_700_v1',[699,700],'دو KEEP699 و700؛ ادامه701.',cp['created_utc'])
