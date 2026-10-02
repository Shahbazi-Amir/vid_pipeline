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
    a=decision(370,'تمام ده شاهد خوانده شد. صفر تعریف رده به عنوان سامانه معرفی بهتر خدمات بانکی را مستقیم دارد. پاسخ تنها همین تعریف را می‌گوید و انتخاب بهتر، مجوز، تضمین امنیت یا خدمات فعلی را اضافه نمی‌کند. واژه رده در متن‌های بریده دیگر بخشی از واژه یا رده شغلی است و سامانه دیگری معرفی نمی‌کند.',[[(0,'«رده» سامانۀ معرفی بهتر خدمات بانکی است.','تعریف پاسخ و claim واحد مستقیم و کامل است.')]])
    answer=rows(ROOT/'outputs.jsonl')[370]['response']['answer_text']
    reason='تمام ده شاهد خوانده شد. سؤال نوع نیاز، سن، موقعیت یا مرجع خود بچه را مشخص نمی‌کند. شواهد از آموزش انتخاب و هزینه فرصت، حمایت فرزندان بهزیستی، الگوگیری، کار امن، استقلال مالی، نظرخواهی، تقسیم درآمد و نیازهای کالایی صحبت می‌کنند. هیچ کدام پاسخ یکتایی به این سؤال بدون زمینه نمی‌دهد؛ پاسخ نبود تعیین نیاز در سؤال را می‌گوید و نبود هرگونه توصیه در شواهد را ادعا نمی‌کند.'
    b=decision(371,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)])
    b['audit']['status']='VALID_ABSTENTION';b['support']['abstention_review']='JUSTIFIED';b['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==851
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0026';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[370,371],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0026/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=57,total_reviewed=853,remaining=296,next_position=372)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_370_371_v1',[370,371],'KEEP370 و VALID_ABSTENTION371؛ ادامه372.',cp['created_utc'])
