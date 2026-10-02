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
    ins=rows(ROOT/'inputs.jsonl');outs=rows(ROOT/'outputs.jsonl')
    ev=json.loads(ins[336]['messages'][1]['content'])['evidence'];r=copy.deepcopy(outs[336]['response'])
    r['answer_text']='متن، ده درصد درآمد را به‌عنوان سهم نمونهٔ صندوق اضطراری و سه تا نه برابر درآمد ماهانه را برای اندازهٔ آن مطرح می‌کند؛ این درصد برای همه ثابت نیست.'
    r['claims']=[dict(claim_text='متن ده درصد درآمد را برای صندوق اضطراری و اندازه سه تا نه برابر درآمد ماهانه را مطرح می‌کند.',claim_type='FACTUAL',evidence_ids=[ev[3]['evidence_id'],ev[4]['evidence_id']]),dict(claim_text='درصد صندوق‌ها در متن برای همه ثابت نیست و نمونه است.',claim_type='FACTUAL',evidence_ids=[ev[5]['evidence_id']])]
    a=decision(337,'تمام ده شاهد خوانده شد. پاسخ اولیه فقط نه برابر را می‌گفت؛ شواهد اول تا چهارم بازه سه تا نه را تصریح می‌کنند و پنجم درصدها را نمونه و وابسته به شرایط می‌داند. پاسخ و دو claim با بازه، ماهانه بودن و غیرثابت بودن درصدها اصلاح و دوباره با سوم، چهارم و پنجم تطبیق شدند. ناسازگاری جمع درصدهای صندوق‌ها در چهارم برای این پرسش اضطراری لازم نیست و جمع‌بندی نشده است. هزینه و درآمد در ششم گزینه‌های قاعده سرانگشتی‌اند، نه مساوی بودن همیشگی آنها.',[
      [(3,'صندوق اضطراری\n: 10 درصد درآمد.','سهم درآمد برای صندوق اضطراری صریح است.'),(4,'اندازۀ صندوق اضطراری دست‌ِکم 3 و دستِ‌بالا ۹ برابر درآمد ماهانه است','دو حد و واحد درآمد ماهانه مستقیم‌اند.')],
      [(5,'این درصدها حکم ثابت برای همه نیست. من برای جاافتادن مفهوم مثال می‌زنم پنج درصد، ده درصد، پنج درصد. ممکنه برای شما یک درصد، سه درصد، دو درصد مناسب باشه.','درصدهای گفته‌شده نمونه‌اند و حکم ثابت همگانی ندارند.')]],repair=r,dimensions={
      'evidence_sufficiency':'سهم، هر دو حد، واحد ماهانه و نمونه بودن در شواهد مستقیم‌اند.',
      'question_answer_fit':'سهم و اندازه صندوق با رفع حذف حد پایین پاسخ داده شد.',
      'factual_claim_support':'دو claim تمام پاسخ، مقدار و قید نمونه بودن را پوشش می‌دهند.',
      'scope_modality_negation_quantity':'سه تا نه برابر درآمد ماهانه است؛ ده درصد نمونه و غیرثابت است.',
      'outside_details':'توصیه شخصی یا قاعده قطعی برای وضعیت کاربر اضافه نشده.',
      'abstention_justified':'NOT_APPLICABLE',
      'ambiguity_conflict':'چهارم جمع سهم همه صندوق‌ها ناسازگار دارد؛ جمع آنها ادعا نشده. تفاوت هزینه و درآمد در ششم و هفتم ثبت و پاسخ فقط مبنای درآمد ماهانه را گزارش می‌کند.'})
    a['audit']['error_categories']=['omitted lower bound','omitted modality']
    a['repair']['reason_fa']='حد پایین سه برابر و نمونه بودن درصدها حذف شده بود؛ به پاسخ و claims فعال افزوده شد.'
    a['repair']['recheck_reason_fa']='هر دو حد و واحد ماهانه و ده درصد و غیرثابت بودن با سوم تا پنجم دوباره تطبیق شدند.'
    ev=json.loads(ins[337]['messages'][1]['content'])['evidence'];r=copy.deepcopy(outs[337]['response'])
    r['answer_text']='طبق متن، عرضهٔ محصولات مالی در بازار پول، سرمایه و بیمه افزایش یافته است.'
    r['claims']=[dict(claim_text=r['answer_text'],claim_type='FACTUAL',evidence_ids=[ev[4]['evidence_id']])]
    b=decision(338,'تمام ده شاهد خوانده شد. امتناع اصلی نادرست بود: شاهد چهارم دقیقاً افزایش عرضه محصولات مالی در هر سه بازار سؤال را می‌گوید. دوم نیز افزایش عرضه و تقاضا را جدا شرح می‌دهد؛ تقاضا برای تأمین مالی جمله دیگری است و با عرضه خلط نمی‌شود. پاسخ به عرضه محصولات طبق متن اصلاح شد و claim تازه با چهارم دوباره تطبیق شد. ارقام شمول، کد بورسی و فراوانی سرمایه‌گذاری در شواهد دیگر پاسخ متغیر مورد سؤال نیستند.',[[(4,'افزایش عرضهٔ محصولات مالی در بازار پول، سرمایه و بیمه','افزایش، عرضه محصولات و نام هر سه بازار عیناً آمده‌اند.')]],repair=r,dimensions={
      'evidence_sufficiency':'چهارم پاسخ صریح برای هر سه بازار دارد.',
      'question_answer_fit':'متغیر عرضه محصولات که در بازارهای نام‌برده افزایش یافته مشخص شد.',
      'factual_claim_support':'claim تازه تمام پاسخ با انتساب متن را پوشش می‌دهد.',
      'scope_modality_negation_quantity':'افزایش عرضه گزارش متن است؛ مقدار عددی یا بازه زمانی جدید ندارد.',
      'outside_details':'آمار جاری بازارها یا علت بیرونی اضافه نشده.',
      'abstention_justified':'ORIGINAL_NOT_JUSTIFIED_REPAIRED',
      'ambiguity_conflict':'دوم عرضه و تقاضا را جدا دارد؛ چهارم همان عرضه را در هر سه بازار نام می‌برد. شمول مالی و فراوانی سرمایه‌گذاری شاخص‌های متفاوت‌اند.'})
    b['audit']['error_categories']=['unsupported abstention']
    b['repair']['reason_fa']='با وجود پاسخ صریح در شاهد چهارم، پاسخ اولیه امتناع کرده بود؛ پاسخ و claim عرضه محصولات جایگزین شدند.'
    b['repair']['recheck_reason_fa']='پاسخ فعال با عبارت صریح چهارم دوباره بررسی شد؛ عرضه با تقاضا و شمول خلط نشده است.'
    return [a,b]

if __name__=='__main__':
    work=Path(__file__).resolve().parent;ds=decisions();a=range_io.assignment('auditor_1');ins,outs=frozen.source_rows()
    for d in ds:range_io.strict_decision(d,a,ins,outs)
    c,previous=frozen.verify_current();assert c['semantic_complete']==818
    state=frozen.append_decisions(previous,ds);frozen.preserve(previous,state);counts=frozen.validate(state,ins,outs)
    pointer=json.loads((work/'CURRENT.json').read_text());directory=work/'batches/batch_0011';assert not directory.exists();directory.mkdir()
    save(directory/'decisions.jsonl',ds,True)
    for n,v in [('audit.jsonl',[d['audit'] for d in ds]),('support.jsonl',[d['support'] for d in ds]),('repairs.jsonl',[d['repair'] for d in ds if 'repair' in d])]:save(directory/n,v,True)
    save(directory/'validation.json',dict(**counts,revision_hash_spans='PASS',method='AGENT_REVIEW',independent=False,source_location='NOT_RUN',nb19_adapter='NOT_RUN',nb20_handoff='NOT_RUN'))
    cp=dict(owner='coordinator',run_id='coordinator_resume_v1',base_commit=pointer['base_commit'],previous_batches=pointer['batches'],positions=[337,338],candidate_ids=[d['audit']['candidate_id'] for d in ds],files={p.name:sha(p.read_bytes()) for p in directory.iterdir()},created_utc=datetime.now(timezone.utc).isoformat())
    save(directory/'checkpoint.json',cp)
    assert frozen.validate(frozen.append_decisions(previous,rows(directory/'decisions.jsonl')),ins,outs)==counts
    pointer['batches'].append(dict(path='batches/batch_0011/checkpoint.json',sha256=sha((directory/'checkpoint.json').read_bytes())))
    pointer['completed_candidate_ids']+=cp['candidate_ids'];pointer.update(new_reviewed=24,total_reviewed=820,remaining=329,next_position=339)
    save(work/'CURRENT.json',pointer)
    frozen.publish(state,'coordinator_resume_337_338_v1',[337,338],'دو اصلاح337 و338؛ ادامه339.',cp['created_utc'])
