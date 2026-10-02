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
    a=decision(380,'تمام ده شاهد خوانده شد. صفر ثبت ردیف‌ها را راه دیدن تقریب هزینه ماهانه هر بخش و مقدمه بررسی کاهش، حذف یا جابه‌جایی در بودجه می‌گوید. پاسخ مبنا را می‌گوید نه کاهش خودکار صرف نوشتن. اول و هشتم بودجه پیش از هزینه و سوم تناسب سبک زندگی را دارند؛ افزایش یک ردیف در نهم با پاسخ تضاد ندارد چون کاهش یا حذف تنها کاربرد ادعا نشده است.',[[(0,'وقتی این ردیف‌ها را یادداشت می‌کنیم، می‌بینیم تقریباً در هر بخش ماهانه چقدر هزینه داریم. بعد تازه می‌تونیم وارد بودجه بشیم؛ یعنی پس از سه ماه فکر کنیم کدام هزینه قابل کاهش است، کدام قابل حذف و کدام قابل جابه‌جایی. بودجه ابزار بعدیه و مقدمه‌اش همین نوشتنه.','دیدن هزینه هر بخش و فراهم کردن مبنای بودجه و بررسی کاهش یا حذف همه مستقیم‌اند.')]])
    b=decision(381,'تمام ده شاهد خوانده شد. صفر هدف الگوی موسوم زنانه را خرید هیجانی برای از بین بردن تنش عاطفی تعریف می‌کند. سؤال هدف را می‌پرسد و پاسخ کاهش تنش می‌گوید، نه درمان مؤثر یا حل ریشه مسئله. سوم و ششم بهتر شدن موقت حال همراه هزینه و باقی بودن مسئله را توضیح می‌دهند؛ اول، ششم، هشتم و نهم نام را غیرانحصاری جنسیتی می‌دانند. پاسخ درباره الگوی نام‌گذاری‌شده است نه همه زنان.',[[(0,'الگوی زنانه؛ خرید هیجانی برای از بین بردن تنش عاطفی','هدف الگو در متن مستقیم است و پاسخ کاهش تنش را مقصود معرفی می‌کند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==861
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0032';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[380,381],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0032/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=67,total_reviewed=863,remaining=286,next_position=382)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_380_381_v1',[380,381],'دو KEEP380 و381؛ ادامه382.',cp['created_utc'])
