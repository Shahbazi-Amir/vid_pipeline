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
    data=json.loads(rows(ROOT/'inputs.jsonl')[391]['messages'][1]['content'])
    r=copy.deepcopy(rows(ROOT/'outputs.jsonl')[391]['response'])
    r['answer_text']='هدف ابتدایی سرمایه‌گذاری در متن، حفظ ارزش پول، به‌ویژه در اقتصاد تورمی است؛ رسیدن سرمایه از ده میلیون به سی میلیون تومان، هدف اول یک نمونهٔ برنامهٔ شخصی است.'
    r['claims'][0]['claim_text']=r['answer_text'];r['claims'][0]['evidence_ids']=[data['evidence'][i]['evidence_id'] for i in [0,1]]
    a=decision(392,'تمام ده شاهد خوانده شد. پاسخ اولیه هدف اول نمونه شخصی صفر را به جای هدف ابتدایی کلی سرمایه‌گذاری پاسخ می‌داد؛ با وجود قید مثال، سؤال کلی را پوشش نمی‌داد. اول هدف ابتدایی را حفظ ارزش پول می‌گوید و دوم و چهارم و پنجم مؤیدند. پاسخ این هدف را اول آورد و عدد نمونه قبلی را به برنامه شخصی محدود کرد. رشد و درآمد و رسیدن هدف مالی مراحل یا مقاصد دیگرند؛ تحقق حفظ ارزش یا سه‌برابر شدن تضمین نشده است.',[[(1,'سرمایه‌گذاری یک هدف ابتدایی دارد و آن حفظ ارزش پول به ویژه در اقتصاد تورمی است.','پاسخ مستقیم به هدف ابتدایی کلی سؤال است.'),(0,'هدف اول، رسیدن اصل سرمایه از ده میلیون تومان به سی میلیون تومان.','عدد نمونه شخصی حفظ شده ولی از هدف اولیه عام تفکیک شده است.')]],repair=r)
    a['audit']['error_categories']=['example substituted for general objective'];a['repair']['reason_fa']='هدف اول نمونه شخصی جای هدف ابتدایی عام آمده بود؛ حفظ ارزش پول افزوده و مثال محدود شد.';a['repair']['recheck_reason_fa']='هدف کلی با اول و هدف نمونه با صفر دوباره تطبیق شدند؛ هدف با تضمین بازده یکی نشد.'
    b=decision(393,'تمام ده شاهد خوانده شد. صفر سه مشکل اتکای صرف به افزایش درآمد را دشواری و زمان و معمولاً همراه شدن بخشی از افزایش درآمد با افزایش هزینه می‌گوید. پاسخ همان سه را با معمولاً خلاصه کرده و افزایش هزینه را همگانی یا اجتناب‌ناپذیر نکرده است. اول و دوم و سوم و پنجم و نهم مؤید و قید عدم مدیریت هزینه را شرح می‌دهند؛ مشکلات قرض و سقف درآمد ناشی از شغل و کلاهبرداری موضوعات دیگری‌اند.',[[(0,'پس اگر فقط روی افزایش درآمد تکیه کنیم، سه مشکل داریم: افزایش درآمد دشوار است، زمان می‌برد و معمولاً بخشی از افزایش درآمد با افزایش هزینه همراه می‌شود.','شرط اتکای صرف و هر سه مشکل و قید معمولاً مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==873
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0038';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[392,393],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0038/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=79,total_reviewed=875,remaining=274,next_position=427)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_392_393_v1',[392,393],'REPAIRED392 و KEEP393؛ ادامه427.',cp['created_utc'])
