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
    a=decision(678,'تمام ده شاهد خوانده شد. صفر هر چهار تجربه پاسخ را مستقیم بیان می‌کند. اول و پنجم و ششم شرایط مبلغ و نظم پرداخت و همراهی را توضیح می‌دهند؛ پاسخ می‌توانند تجربه کنند است و هر مبلغ یا پرداخت بی‌قاعده را تضمین آموزشی نمی‌داند. اختلاف سوم و هشتم درباره پرداخت کار منزل در پاسخ وارد نشده است.',[[(0,'دریافت پول توجیبی به کودکان مدیریت دخل\u200cوخرج، بودجه\u200cبندی و درک ارزش دارایی\u200cها را می\u200cآموزد.\nتجربه مسئولیت\u200cپذیری را به همراه دارد.','مدیریت دخل‌وخرج و بودجه‌بندی و ارزش دارایی و مسئولیت‌پذیری همه صریح‌اند.')]])
    b=decision(679,'تمام ده شاهد خوانده شد. چهارم درباره فرد بیکار و کار ولو بدون درآمد می‌گوید تجربه و دانش و مهارت ذخیره می‌شود و هیئت و مسجد و بنیاد خیریه را بستر کارورزی و آمادگی بازار کار مثال می‌زند. هفتم ادامه و فرصت تجربه است؛ پاسخ فرصتی ممکن می‌گوید نه تضمین حقوق یا اشتغال و نه کمک نقدی مستقیم همه خیریه‌ها.',[[(4,'احتمالاً اون تجربه و دانش و مهارتیه که در واقع ذخیره می‌شه.','کسب تجربه و مهارت هدف فعالیت است.'),(4,'ما مثلاً کارهای عام‌المنفعه داریم که بالاخره نمی‌دونم از هیئت و مسجد، نمی‌دونم بنیادهای خیریه بگی، که آدم اونجا ورز داده می‌شه؛ یعنی یه جور کارورزی می‌کنه و آماده حضور در بازار کار یا...','کارورزی و آمادگی حضور در بازار کار با مثال هیئت و بنیاد خیریه مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==893
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0048';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[678,679],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0048/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=99,total_reviewed=895,remaining=254,next_position=680)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_678_679_v1',[678,679],'دو KEEP678 و679؛ ادامه680.',cp['created_utc'])
