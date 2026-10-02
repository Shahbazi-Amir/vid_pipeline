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
    a=decision(670,'تمام ده شاهد خوانده شد. صفر ارزش فعلی پول در زمان حال را خود مبلغ می‌گوید و مثال ده میلیارد دارد. سایر شواهد تنزیل جریان آتی، تورم و قدرت خرید تاریخی یا هزینه فرصت را بیان می‌کنند؛ پاسخ برابری ارزش فعلی در همان زمان را می‌گوید و ثبات قدرت خرید در آینده را ادعا نمی‌کند.',[[(0,'خب، ارزش فعلی هر پولی که حالاست، خودش؛ بنابراین ده میلیارد.','ارزش فعلی مبلغ زمان حال همان مبلغ است؛ دوره تنزیل صفر است.')]])
    answer=rows(ROOT/'outputs.jsonl')[670]['response']['answer_text'];reason='تمام ده شاهد خوانده شد. سؤال ویژگی فرآیند خرید را بدون مشخص کردن ویژگی یا الگو می‌پرسد. صفر و اول و هشتم الگوهای متنوع خرید، پنجم اثر تبلیغات، ششم لزوم آگاهی در تصمیم مالی و نهم نیاز و خواسته را شرح می‌دهند؛ ویژگی واحد و منحصر فرآیند خرید تعریف نشده است. پاسخ فقط تعیین ویژگی واحد را ناممکن می‌داند، نه نبود هرگونه اطلاعات خرید. نسبت دادن زمان‌بر و روشمند بودن کسب ثروت در دوم یا همزمانی تولید و فروش خدمت در سوم به خرید نادرست است.'
    b=decision(671,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)]);b['audit']['status']='VALID_ABSTENTION';b['support']['abstention_review']='JUSTIFIED';b['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==885
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0044';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[670,671],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0044/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=91,total_reviewed=887,remaining=262,next_position=672)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_670_671_v1',[670,671],'KEEP670 و VALID_ABSTENTION671؛ ادامه672.',cp['created_utc'])
