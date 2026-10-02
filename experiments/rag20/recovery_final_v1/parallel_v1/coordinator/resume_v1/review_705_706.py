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
    data=json.loads(rows(ROOT/'inputs.jsonl')[704]['messages'][1]['content']);answer='در برنامهٔ توسعهٔ مؤسسهٔ تینک‌فوروارد، سه مؤلفهٔ رشد، تلنگر و فناوری بررسی می‌شوند: تعداد کاربران، تشویق رفتار مالی درست و ارتقای زیرساخت‌ها یا افزودن امکانات فنی.';r=dict(answer_text=answer,claims=[dict(claim_text=answer,claim_type='FACTUAL',evidence_ids=[data['evidence'][0]['evidence_id']])])
    a=decision(705,'تمام ده شاهد خوانده شد. صفر سه معیار و معنای آنها را برای برنامه توسعه تینک‌فوروارد می‌گوید، نه قانون انتخاب همه استارتاپ‌ها. دیگر شواهد تعریف استارتاپ و سبک شغلی و تصمیم شخصی هستند؛ پاسخ به برنامه مشخص مقید شد و سه معیار و شرحشان حفظ شد.',[[(0,'«برنامۀ توسعه» یکی از برنامه‌های سال جاری مؤسسه است که به شناسایی، انتخاب و توسعۀ استارت‌آپ‌های سلامت مالی می‌پردازد.','دامنه برنامه توسعه مؤسسه روشن است.'),(0,'در انتخاب استارت\u200cآپ\u200cها و اپلیکیشن\u200cهای برتر، سه مؤلفه مورد بررسی قرار می\u200cگیرند؛ رشد،\nتلنگر\nو فناوری. بخش رشد، بر تعداد کاربران اپلیکیشن\u200cها تمرکز دارد. در بخش دوم، توسعۀ رفتار مالی درست و ترغیب کاربران با اجرای تلنگرها مورد توجه قرار می\u200cگیرد.','رشد و تلنگر و فناوری و دو شرح نخست مستقیم‌اند.'),(0,'در بخش فناوری، ارتقای زیرساخت‌ها یا افزودن مشخصات فنی جدید، بررسی می‌شود.','شرح فناوری مستقیم است.')]],repair=r);a['audit']['error_categories']=['missing program scope'];a['repair']['reason_fa']='معیارهای برنامه خاص به همه استارتاپ‌ها تعمیم داده نشد و نام برنامه افزوده شد.';a['repair']['recheck_reason_fa']='دامنه و هر سه معیار با صفر دوباره تطبیق شد.'
    b=decision(706,'تمام ده شاهد خوانده شد. صفر مسیر رشد را غیرخطی و اصلاح با تجربه و بازخورد می‌گوید؛ چهارم تمرین و نهم ندانستن و ناتوانی فرصت رشد را توضیح می‌دهند. پاسخ ابزار اصلاح مسیر را می‌گوید نه تضمین نتیجه یا بی‌نیازی از هدف و برنامه.',[[(0,'مسیر رشد هم خط صاف نیست؛ با تجربه و بازخورد اصلاح می‌شه.','دو عامل اصلاح مستقیم‌اند.')]])
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==920
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0061';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[705,706],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0061/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=126,total_reviewed=922,remaining=227,next_position=707)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_705_706_v1',[705,706],'REPAIRED705 و KEEP706؛ ادامه707.',cp['created_utc'])
