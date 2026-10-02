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
    a=decision(691,'تمام ده شاهد خوانده شد. صفر مقدار شکاف فقر و تفسیر کالری خانوار فقیر نسبت به حداقل روزانه را مستقیم می‌گوید؛ پاسخ طبق متن مقید است و نسبت را سهم جمعیت فقیر یا آمار امروز نمی‌نامد. درصدهای بیمه و شمول مالی جامعه و شاخص دیگری‌اند؛ با پانزده ممیز دو خلط نشده‌اند.',[[(0,'شکاف فقر در ایران 15/2درصد است؛ به عبارت دیگر کالری دریافتی خانوارهای فقیر، 15/2درصد کم\u200cتر از حداقل کالری موردنیاز روزانه است.','عدد و معنای کالری و جامعه خانوارهای فقیر مستقیم‌اند.')]])
    data=json.loads(rows(ROOT/'inputs.jsonl')[691]['messages'][1]['content']);first='خرید نسیه نوعی بدهکارشدن است و مشمول قواعد قرض می‌شود؛';second=' خرید نسیهٔ کالای بادوام یا سرمایه‌ای با رعایت این قواعد، «پس‌انداز معکوس» نام دارد.';answer=first+second
    r=dict(answer_text=answer,claims=[dict(claim_text=first,claim_type='FACTUAL',evidence_ids=[data['evidence'][5]['evidence_id']]),dict(claim_text=second.strip(),claim_type='FACTUAL',evidence_ids=[data['evidence'][4]['evidence_id']])])
    b=decision(692,'تمام ده شاهد خوانده شد. صفر بحث نسیه را مقدمه ورود به اهرم‌سازی می‌آورد ولی تعریف این دو را یکی نمی‌کند. چهارم اهرم را کاربرد بدهی با بازده بیشتر از هزینه و پس‌انداز معکوس را نسیه کالای بادوام و سرمایه‌ای با رعایت قواعد می‌داند؛ پنجم نسیه را بدهکار شدن و مشمول قواعد قرض می‌گوید. پاسخ قبلی ارتباط بحثی را جای طبقه‌بندی دقیق نشانده بود؛ اصلاح دو مفهوم را جدا و شرط کالای بادوام و رعایت قواعد را حفظ کرد.',[[(5,'یادتون باشه خرید نسیه یه جوری در واقع همین بدهکار شده نده\nدرسته ما می\u200cخریم مثل همین پس\u200cانداز معکوس\nو اتا کارتهای اعتباری\nهر دو اینا مشمول همون قواعد قرض هست','نسیه بدهکارشدن و مشمول قواعد قرض است.')],[(4,'پس انداز معکوس: خرید نسیه کالای بادوام و سرمایه‌ای با رعایت قواعد قرض به عنوان قلکی برای پس‌انداز در شرایط تورمی.','نام پس‌انداز معکوس و شرایط کالا و قواعد مستقیم‌اند.')]],repair=r,units=[dict(text=first,kind='FACTUAL',claim_indices=[0],reason_fa='بدهکار شدن و رعایت قواعد'),dict(text=second,kind='FACTUAL',claim_indices=[1],reason_fa='نام پس‌انداز معکوس با شروط')])
    b['audit']['error_categories']=['concept conflation','omitted conditions'];b['repair']['reason_fa']='خرید نسیه با اهرم‌سازی یکی نیست؛ تعریف بدهی و پس‌انداز معکوس با شرایط جایگزین شد.';b['repair']['recheck_reason_fa']='هر دو ادعا جدا با پنجم و چهارم تطبیق شد؛ شرط بازده اهرم به تعریف نسیه تعمیم نیافت.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==906
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0054';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[691,692],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0054/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=112,total_reviewed=908,remaining=241,next_position=693)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_691_692_v1',[691,692],'KEEP691 و REPAIRED692؛ ادامه693.',cp['created_utc'])
