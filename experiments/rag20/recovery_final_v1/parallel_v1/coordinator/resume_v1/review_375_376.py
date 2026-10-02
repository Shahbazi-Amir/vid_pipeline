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
    a=decision(375,'تمام ده شاهد خوانده شد. صفر قسمت بیست و پنجم را با موضوع سواد مالی و فناوری‌های نرم در29 بهمن99 مشخص می‌کند. پاسخ99 را به1399 باز می‌کند و تاریخ یا موضوع قسمت‌های24،26،22،35،23،27،5،29 و20 را با آن مخلوط نمی‌کند. زمان یا سمت مهمان بیرونی اضافه نشده است.',[[(0,'قسمت بیست و پنجم برنامه با موضوع «سواد مالی و فناوری‌های نرم» 29 بهمن‌ماه 99','شماره قسمت و موضوع و روز و ماه و سال پاسخ مستقیم‌اند.')]])
    b=decision(376,'تمام ده شاهد خوانده شد. صفر امکان تبدیل بخشی از درآمد پیش از مصرف کامل به دارایی درآمدزا را صریح می‌گوید. پاسخ می‌تواند را حفظ کرده و همه درآمد یا سود تضمینی یا حفظ قطعی قدرت خرید را نمی‌گوید. متن خودش تورم و بازده واقعی را جدا می‌کند و نام دارایی را بدون نوع استفاده تعیین‌کننده نمی‌داند؛ باقی شواهد صندوق و بدهی و تخصیص درآمد را توضیح می‌دهند و ادعای پاسخ را نقض نمی‌کنند.',[[(0,'فعلاً اصل مفهومی رو بگیریم: قبل از مصرف کامل درآمد، بخشی از اون می‌تونه تبدیل به یک دارایی درآمدزا بشه.','همان مقدار بخشی، زمان پیش از مصرف و امکان تبدیل مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==856
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0029';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[375,376],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0029/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=62,total_reviewed=858,remaining=291,next_position=377)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_375_376_v1',[375,376],'دو KEEP375 و376؛ ادامه377.',cp['created_utc'])
