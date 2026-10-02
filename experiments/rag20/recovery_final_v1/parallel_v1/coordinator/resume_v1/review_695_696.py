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
    a=decision(695,'تمام ده شاهد خوانده شد. صفر تعریف قضاوت یک حوزه بر اساس شکست یا موفقیت حوزه دیگر را مستقیم می‌آورد و اول تکرار می‌کند. مثال فقر و ثروت و پزشک کاربرد همین خطاست، نه تعریف همه اثرهای شناختی. اثر رژلب دوم و مطالب انرژی هشتم موضوعات جدا هستند و به تعریف افزوده نشده‌اند.',[[(0,'اثر هاله‌ای، پیش‌داوری یا قضاوت دربارهٔ رفتار یک فرد در یک حوزه از زندگی، بر اساس شکست یا موفقیت او در حوزهٔ دیگر است.','تعریف کامل مستقیم است.')]])
    data=json.loads(rows(ROOT/'inputs.jsonl')[695]['messages'][1]['content']);r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[695]['response']);r['claims'][0]['evidence_ids']=[data['evidence'][i]['evidence_id'] for i in [0,9]]
    b=decision(696,'تمام ده شاهد خوانده شد. صفر بررسی تحقق بودجه پایان ماه را کامل می‌گوید اما بخش اصلاح در انتها بریده است. نهم ادامه را کامل می‌گوید و شرط برآورد نادرست و تغییر ردیف یا مبلغ را مستقیم دارد؛ اول و ششم و هشتم هم بازنگری را تأیید می‌کنند. متن پاسخ درست بود ولی استناد صفر به تنهایی همه جزئیات را نمی‌پوشاند؛ شاهد نهم افزوده و پاسخ بدون تغییر حفظ شد.',[[(0,'در پایان ماه دو کار انجام می‌دهیم. اول نگاه می‌کنیم ببینیم چقدر به بودجه عمل کرده‌ایم.','زمان و بررسی میزان تحقق مستقیم است.'),(9,'ممکن است از اول برآوردتان اشتباه بوده باشد. در این حالت باید خود بودجه را تصحیح کنید. ردیف‌ها یا مبلغ آن‌ها را تغییر بدهید و برای ماه بعد برنامه واقع‌بینانه‌تری بنویسید.','شرط خطای برآورد و تغییر ردیف یا مبلغ مستقیم است.')]],repair=r)
    b['audit']['error_categories']=['incomplete citation coverage'];b['repair']['reason_fa']='متن پاسخ حفظ شد و شاهد نهم برای جزئیات اصلاح بودجه به استناد افزوده شد.';b['repair']['recheck_reason_fa']='تحقق پایان ماه با صفر و شرط اصلاح ردیف و مبلغ با نهم کامل بررسی شد.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==910
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0056';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[695,696],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0056/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=116,total_reviewed=912,remaining=237,next_position=697)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_695_696_v1',[695,696],'KEEP695 و REPAIRED696؛ ادامه697.',cp['created_utc'])
