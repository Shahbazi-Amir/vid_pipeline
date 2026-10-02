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
    answer=rows(ROOT/'outputs.jsonl')[688]['response']['answer_text'];reason='تمام ده شاهد خوانده شد. شخص یا نوع وام در سؤال مشخص نیست. اول ده میلیون شش ماه یا قسط ده ماه، دوم چند فرد و مبالغ متفاوت، سوم تسهیلات مسکن و چهارم ده میلیون چهار ماه را مثال می‌زنند؛ هیچ شخص یکتایی برای تعیین جفت مبلغ و مدت سؤال شناخته نمی‌شود. پاسخ نبود مقدار مشخص وام مورد سؤال را می‌گوید، نه نبود هیچ مثال عددی در شواهد.'
    a=decision(689,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)]);a['audit']['status']='VALID_ABSTENTION';a['support']['abstention_review']='JUSTIFIED';a['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    answer=rows(ROOT/'outputs.jsonl')[689]['response']['answer_text'];reason='تمام ده شاهد خوانده شد. صفر و دوم و نهم معیار انتخاب و بازدید خانه و اول اطلاعات واسطه بازار و هفتم دارایی‌ها و جریان پولی را شرح می‌دهند؛ رابطه صریح اطلاعات نوع ماشین و مکان خانه با یک نتیجه معین مانند درآمد یا اعتبار شخص ارائه نشده است. نتیجه‌گیری از ظاهر دارایی درباره ثروت فرد نیازمند فرض بیرونی است. پاسخ محدود به نامشخص بودن نتیجه همین اطلاعات موجه است.'
    b=decision(690,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)]);b['audit']['status']='VALID_ABSTENTION';b['support']['abstention_review']='JUSTIFIED';b['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==904
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0053';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[689,690],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0053/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=110,total_reviewed=906,remaining=243,next_position=691)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_689_690_v1',[689,690],'دو VALID_ABSTENTION689 و690؛ ادامه691.',cp['created_utc'])
