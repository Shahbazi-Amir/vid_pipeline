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
    data=json.loads(rows(ROOT/'inputs.jsonl')[378]['messages'][1]['content'])
    answer='طبق متن، زیاد بودن مبلغ پول‌توجیبی یا درخواست دوبارهٔ پول پیش از موعد و هر بار پس از تمام شدن آن، به ولخرج و بی‌مسئولیت بار آمدن فرزندان نسبت داده شده است.'
    r=dict(answer_text=answer,claims=[dict(claim_text=answer,claim_type='FACTUAL',evidence_ids=[data['evidence'][0]['evidence_id']])])
    d=decision(379,'تمام ده شاهد خوانده شد. صفر علت مورد سؤال را صریح در جمله کامل گفته است؛ بریدگی انتهای شاهد مربوط به توصیه مقدار مناسب است و علت قبلی را ناقص نمی‌کند. امتناع اولیه ناموجه بود. پاسخ به گزارش متن مقید شد و دو حالت مبلغ زیاد یا درخواست زودهنگام پس از اتمام را جدا حفظ کرد. کم بودن پول با سرخوردگی مرتبط است نه همین علت؛ فقر کودک کار در چهارم بی‌مسئولیتی خانواده نیست و با پول‌توجیبی خلط نشد.',[[(0,'در نقطۀ مقابل، اگر مبلغ پول‌توجیبی زیاد باشد یا فرزندان قبل از موعد و با هر بار تمام شدن پول‌توجیبی، مبلغی را درخواست کنند، آن‌ها ولخرج و بی‌مسئولیت بار خواهند آمد.','هر دو حالت با یا و هر دو پیامد در جمله کامل مستقیم‌اند؛ پاسخ نسبت دادن متن را گزارش می‌کند.')]],repair=r)
    d['audit']['error_categories']=['unsupported abstention']
    d['repair']['reason_fa']='علت در شاهد صفر کامل و روشن بود؛ پاسخ ناموجه نبود شواهد به دو حالت صریح متن تبدیل شد.'
    d['repair']['recheck_reason_fa']='claim تازه و همه پاسخ با جمله شرطی کامل صفر تطبیق شدند؛ ارتباط کم بودن مبلغ با سرخوردگی و فقر کودک کار جدا ماندند.'
    return [d]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==860
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0031';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[379],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0031/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=65,total_reviewed=861,remaining=288,next_position=380)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_379_v1',[379],'REPAIRED379؛ ادامه380.',cp['created_utc'])
