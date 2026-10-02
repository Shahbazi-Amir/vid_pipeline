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
    a=decision(390,'تمام ده شاهد خوانده شد. صفر در ترتیب مورد سؤال مبلغی برای کمک به دیگران و خرید هدیه را می‌گوید و پاسخ همین دو مصرف را دارد. درصد پنج در برخی مدل‌ها و تخصیص پیش از خرج در دوم و چهارم و نهم چارچوب دیگر است؛ سؤال با همان ترتیب صفر آمده و پاسخ مقدار ثابت یا ترتیب همگانی نگفته است. صندوق اضطراری و هدف سرمایه‌گذاری با مبلغ یاری دیگران خلط نشده‌اند.',[[(0,'توصیه می‌شود پس از کنار گذاشتن مخارج، پس‌انداز و پس‌انداز اضطراری، مبلغی برای کمک به دیگران و خرید هدیه در نظر بگیریم.','با شرط و ترتیب خود سؤال، هر دو مصرف جواب مستقیم‌اند و عددی در این عبارت نیست.')]])
    b=decision(391,'تمام ده شاهد خوانده شد. صفر جریان وجوه نقد را در فهرست سه گزارش حسابداری کنار ترازنامه و سود و زیان نام می‌برد. هشتم مفهوم نقد در مقابل سود ثبت‌شده را روشن می‌کند. پاسخ فقط نوع گزارش را می‌گوید؛ جریان درآمد صندوق، گزارش اعتباری، گزارش اخبار و افشای کدال در سایر شواهد جای این اصطلاح ننشسته‌اند. ویژگی گزارش لحظه‌ای ترازنامه به جریان نقد نسبت داده نشده است.',[[(0,'به نظرم از گزارش‌های حسابداری سه تا گزارش رو می‌شه برای شما توضیح داد.','دسته گزارش‌ها صریحاً حسابداری است.'),(0,'یکی جریان وجوه\nنقد.','جریان وجوه نقد در همان فهرست آمده است و پوشش نوع گزارش کامل می‌شود.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==871
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0037';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[390,391],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0037/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=77,total_reviewed=873,remaining=276,next_position=392)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_390_391_v1',[390,391],'دو KEEP390 و391؛ ادامه392.',cp['created_utc'])
