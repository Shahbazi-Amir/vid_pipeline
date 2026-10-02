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
    a=decision(707,'تمام ده شاهد خوانده شد. صفر ادامه عبارت والدین و مادرها و افتتاح حساب کودک را بیان می‌کند؛ موضوع آموزش کودک و نقش پدر و مادر روشن است. شرایط حقوقی دقیق حساب بانکی در مجموعه نیست و تنظیم حساب کاربری بنکارو در ششم شرط بانکی نیست. پاسخ روایت والدین را با صلاحیت قانونی همه افراد خلط نکرده است.',[[(0,'و مادرها حساب بانکی شخصی برای کودکان باز می‌کنند.','افتتاح حساب کودک در روایت والدین است؛ عبارت آغاز قطعه بریده است.')]],units=[dict(text='در متن، پدر و مادرها برای کودکان حساب بانکی شخصی باز می‌کنند؛',kind='FACTUAL',claim_indices=[0],reason_fa='روایت والدین'),dict(text=' شرایط حقوقی دقیق افتتاح حساب بیان نشده است.',kind='EVIDENCE_LIMITATION',claim_indices=[],reason_fa='شرایط حقوقی بانکی کامل در ده شاهد نیست')])
    b=decision(708,'تمام ده شاهد خوانده شد. صفر اثر زمان و پیوستگی واریز سالانه را مستقیم توضیح می‌دهد و نهم تفاوت افق ده و بیست سال و واریز هر سال را تأیید می‌کند. اول نرخ و سرمایه اولیه هم در فرمول اثر دارند؛ پاسخ عوامل زمان و پیوستگی را می‌گوید نه انحصار عوامل و نه تضمین سود واقعی یا قدرت خرید. اختلاف عدد سناریوهای دیگر در پاسخ وارد نشده است.',[[(0,'هدف این مثال، نه تضمین یک نرخ بازده ثابت، بلکه نشان‌دادن اثر زمان و سود مرکب است.','اثر مدت مستقیم است.'),(0,'پیوستگی، یعنی ادامه‌دادن این کار در طول زمان. اهمیت این دو عامل به مفهوم سود ساده و سود مرکب برمی‌گردد.','پیوستگی و اثر آن مستقیم است.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==922
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0062';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[707,708],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0062/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=128,total_reviewed=924,remaining=225,next_position=709)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_707_708_v1',[707,708],'دو KEEP707 و708؛ ادامه709.',cp['created_utc'])
