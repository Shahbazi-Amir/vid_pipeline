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
    a=decision(676,'تمام ده شاهد خوانده شد. صفر اطلس درآمدی مناطق را در دو سال مقایسه می‌کند و برای آمریکای لاتین و کارائیب نه و چهل و چهار درصد می‌گوید؛ پاسخ طبق متن مقید و اعداد و سال‌ها دقیق‌اند. آمار بورس و سواد مالی و پیام پس‌انداز دیگر شواهد جامعه و سنجه دیگری دارند و با سهم طبقه درآمدی خلط نشده‌اند.',[[(0,'سهم آمریکای لاتین و کارائیب، در کشورهای پردرآمد، از 9درصد در سال 1987 به 44درصد در سال 2023 افزایش یافته','دو سهم و ترتیب دو سال مستقیم‌اند؛ بافت کل بند طبقه درآمدی کشورهای مناطق است.')]])
    b=decision(677,'تمام ده شاهد خوانده شد. صفر ثروتمندی سرمایه‌گذار از فقر کارگر را تحلیل نقل‌شده می‌داند و بلافاصله غفلت آن از پس‌انداز و ریسک و بهره‌وری را نقد می‌کند. پاسخ هر دو بخش و انتساب به متن را حفظ کرده و دیدگاه مورد نقد را واقعیت قطعی نمی‌گوید. سایر شواهد آثار جسمی و اجتماعی فقر و کودک کار هستند؛ نقد کلیه وضعیت‌های استثمار یا انکار هر اثر فقر از آنها نتیجه نگرفته است.',[[(0,'در واقع، از فقر کارگر، ثروتمند می‌شود. چنین تحلیلی نشان می‌دهد پس‌انداز و ریسک و بهره‌وری الف دیده نشده است.','دیدگاه نقل‌شده و نقد سه عامل کنار هم صریح‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==891
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0047';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[676,677],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0047/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=97,total_reviewed=893,remaining=256,next_position=678)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_676_677_v1',[676,677],'دو KEEP676 و677؛ ادامه678.',cp['created_utc'])
