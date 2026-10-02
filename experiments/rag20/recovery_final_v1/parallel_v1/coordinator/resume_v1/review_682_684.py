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
    a=decision(682,'تمام ده شاهد خوانده شد. صفر عدم کفایت درآمد بالا و لزوم تفکیک هزینه شخصی از هزینه کسب‌وکار و فروش از سود را مستقیم توضیح می‌دهد؛ دوم و سوم تفاوت موفقیت و ثروت و ششم مدیریت هزینه را پشتیبانی می‌کنند. پاسخ سود واقعی و خرج شخصی را جدا می‌سنجد، نه اینکه هر کسب‌وکار با فروش زیاد حتماً شکست خورده است.',[[(0,'درآمد زیاد به‌تنهایی موفقیت نیست.','پاسخ منفی مستقیم است.'),(0,'اگر همه این‌ها رو توی یک کیسه بریزیم، دیگه نمی‌فهمیم **کسب‌وکار خودش سودآور بوده یا نه**. هزینه زندگی شخصی با هزینه کسب‌وکار فرق داره.','تفکیک هزینه زندگی و کسب‌وکار ضروری است.'),(0,'باید فرق **فروش، هزینه، سود و وضعیت مالی کسب‌وکار** رو دقیق‌تر ببینیم.','سه سنجه فروش و هزینه و سود مستقیم‌اند.')]])
    answer=rows(ROOT/'outputs.jsonl')[682]['response']['answer_text'];reason='تمام ده شاهد خوانده شد. مرجع تا اینجا در سؤال تعیین نشده است. اول بودجه ماهانه، دوم بانک، سوم برون‌سپاری، چهارم کار داوطلبانه و پنجم کار کودک و درآمد اضافه را شرح می‌دهند؛ اینها یک فهرست مشترک از کارهای انجام‌شده برای یک فعالیت مشخص نیستند. پاسخ ابهام مرجع را بیان می‌کند و نبود همه اطلاعات یا هیچ کاری انجام نشده را ادعا نمی‌کند.'
    b=decision(683,reason,[],units=[dict(text=answer,kind='ABSTENTION',claim_indices=[],reason_fa=reason)]);b['audit']['status']='VALID_ABSTENTION';b['support']['abstention_review']='JUSTIFIED';b['audit']['dimensions']['abstention_justified']='JUSTIFIED'
    c=decision(684,'تمام ده شاهد خوانده شد. دوم سود صد و پنجاه هزار تومان ماهانه برای ده میلیون را مثال هدف ایجاد جریان درآمد می‌داند. پنجم تکرار همین هدف و پرداخت صندوق به اندازه سودآوری است؛ پاسخ در نظر گرفته شده و مثال را حفظ کرده، بازده تحقق‌یافته یا نرخ تضمینی امروز نمی‌گوید. سایر اعداد بازده سی درصد یا افق سی سال سناریوی متفاوت‌اند و خلط نشدند.',[[(2,'برای مثال، ده میلیون تومان سرمایه داریم و می‌خواهیم ماهانه صد و پنجاه هزار تومان سود داشته باشد.','مبلغ اصل و سود ماهانه هدف مثال مستقیم‌اند و وجه مثال حفظ شده است.')]])
    return [a,b,c]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_2');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==897
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0050';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[682,683,684],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0050/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=104,total_reviewed=900,remaining=249,next_position=685)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_682_684_v1',[682,683,684],'KEEP682 و684 و VALID_ABSTENTION683؛ ادامه685.',cp['created_utc'])
