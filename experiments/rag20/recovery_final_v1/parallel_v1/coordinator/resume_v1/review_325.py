"""Full-evidence review of ambiguous position 325."""
import sys,copy,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'parallel_v1/shared'))
from decisions_006_010 import decision
from audit_structure import rows,save,sha
import incremental_review as frozen
import range_io

def decisions():
    reason='هر ده شاهد خوانده شد. سؤال فقط «چه چیزی باید بررسی کنید؟» است و موضوع، موقعیت یا مرجع را مشخص نمی‌کند. شواهد درباره لوازم و ساختمان خانه، هدف و درآمد خرید، پیشنهاد شغلی، مدارک ملکی، بومی‌سازی، هزینه‌فرصت، شخصیت مالی، اوضاع بدهی و تراکنش روزانه‌اند؛ چند پاسخ مختلف واقعاً ممکن است. اول بودن شاهد خانه مجوز نسبت دادن همان موضوع به سؤال نیست. پاسخ فقط این محدودیت و نبود پاسخ یکتا را بیان کرده و ادعای نبود اطلاعات در همه منابع جهان ندارد؛ claims خالی درست است.'
    answer=rows(ROOT/'outputs.jsonl')[324]['response']['answer_text']
    d=decision(325,reason,[],dimensions={
      'evidence_sufficiency':'شواهد متعدد دستور بررسی دارند اما برای انتخاب موضوع سؤال نامشخص کافی نیستند.',
      'question_answer_fit':'امتناع محدود از پاسخ یکتا، متناسب با فقدان مرجع و زمینه سؤال است.',
      'factual_claim_support':'پاسخ ادعای مالی واقعی تازه ندارد؛ claims خالی و تمام پاسخ محدودیت زمینه است.',
      'scope_modality_negation_quantity':'نفی فقط قابل تعیین بودن پاسخ یکتا در همین سؤال و شواهد است، نه نبود تمام پاسخ‌های ممکن.',
      'outside_details':'هیچ موضوع خانه، شغل، ملک یا تراکنش حدس زده نشده.',
      'abstention_justified':'JUSTIFIED',
      'ambiguity_conflict':'ابهام واقعیِ مرجع چه چیزی با چند دستور متفاوت در ده شاهد حل نشده است.'},units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)])
    d['audit']['status']='VALID_ABSTENTION';d['support']['abstention_review']='JUSTIFIED'
    return [d]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==806
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0005';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[325],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0005/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=11,total_reviewed=807,remaining=342,next_position=326)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_325_v1',[325],'امتناع موجه 325 پس از خواندن همه شواهد؛ جمع این نوبت یازده مورد، دو اصلاح؛ ادامه از326.',cp['created_utc'])
