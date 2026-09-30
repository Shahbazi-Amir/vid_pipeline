"""Persist the five explicit full-evidence AGENT_REVIEW decisions; no model calls."""
import copy
from pathlib import Path
from audit_structure import ROOT, rows, save, canonical, sha, validate_schema

def span(evidence, quote):
    start=evidence['text'].index(quote)
    end=start+len(quote)
    assert 0<=start<end<=len(evidence['text']) and evidence['text'][start:end]==quote
    return {'evidence_id':evidence['evidence_id'],'start':start,'end':end,'unit':'UNICODE_CODE_POINT','quote':quote}

def main():
    inputs=rows(ROOT/'inputs.jsonl');outputs=rows(ROOT/'outputs.jsonl')
    reasons={
      1:'پاسخ، مدیریت دخل‌وخرج و درآمد و پس‌انداز را مستقیماً از شاهد اول می‌گیرد و مسئولیت ساختاری دولت را حذف نمی‌کند. شواهد درباره قانون جذب مبنای پاسخ نشده‌اند؛ پاسخ تضمین رفع همه انواع فقر نمی‌دهد.',
      2:'پرسش «خردمند چه ویژگی‌ای دارد؟» کلی و فاقد قید متن است. شاهد سوم، فراموشی تلاش را دور از خرد می‌داند و شاهد چهارم از علم و مال سخن می‌گوید؛ بنابراین نبودن هرگونه حمایت روشن ادعایی بیش از شواهد است. با وجود حمایت جزئی، تعریف یکتای خردمند در همه شواهد مشخص نیست؛ امتناع فعلی معتبر اعلام نمی‌شود و برای رفع ابهام به review می‌رود.',
      3:'هر دو بخش پرسش پاسخ گرفته‌اند: نظم اسناد و ثبت هزینه‌ها در شاهد اول و ششم، و مکتوب‌بودن طلب و بدهی و دارایی و سرمایه و بیمه در شاهد چهارم. توصیه‌های مالیاتی یا امنیتی نامرتبط وارد پاسخ نشده‌اند.',
      4:'شاهد اول زمان چند سال پایانی خدمت، کاهش تدریجی وابستگی هویتی و مالی و بررسی مسیر فعالیت پیش از بازنشستگی را تصریح می‌کند. پاسخ ادعای قطع ناگهانی شغل یا تضمین مالی ندارد.',
      5:'شاهد اول، کاریابی و درآمد را بخش ورودی حوزه مالی می‌نامد و کارکردن را منشأ درآمد توضیح می‌دهد. پاسخ ادعا نمی‌کند که قرض و ارث و سرمایه‌گذاری هیچ ورودی مالی ایجاد نمی‌کنند.'
    }
    quote_specs={
      1:[[(0,'اگر قرار است فرد فقیر نباشد، باید بتواند دخل‌وخرجش را مدیریت کند، درآمد بسازد، پس‌انداز و سرمایه ایجاد کند و به سطحی برسد که دستش به دهانش برسد.')],[(0,'از منظر فردی هم هرکس باید تا جایی که می‌تواند خودش را از چرخه بحران بیرون بکشد؛ اما این جمله نباید به معنی نادیده‌گرفتن مسئولیت دولت و ساختار اقتصادی باشد.')]],
      3:[[(0,'نگهداری اسناد مالی بخشی از نظم مالی و یک تمرین مالی است.'),(0,'مثلاً اگر فرش یا ماشین لباس‌شویی خریده‌اید، فاکتور و ضمانت‌نامه را نگه دارید.'),(5,'نگهداری از اسناد و مدارک علاوه بر نوشتن هزینه ها')],[(3,'چه تو حوزهٔ طلبکاری\nچه تو بدهکاری\nچه تو حوزه دارائی ها، سرمایه ها، بیمه ها و هر چیزی که یک امر مالیه اصولاً باید مکتوب بشه')]],
      4:[[(0,'بهتر است حداقل در چند سال پایانی خدمت جدی‌تر به آن فکر کنیم.'),(0,'منظور این است که وابستگی کامل هویتی و مالی به سازمان را به‌تدریج کم کند و برای مرحله بعد آماده شود.'),(0,'اینها مسیرهایی هستند که باید قبل از روز بازنشستگی بررسی شوند، نه بعد از آن.')]],
      5:[[(0,'یکی از بخش‌های این حوزه مالی، کاریابی و درآمد است؛ یعنی آن ورودی ما، آن ورودی که پول می‌خواهد ازش نشئت بگیرد. ما با کار کردن پول درمی‌آوریم')]]
    }
    audit=[];support=[]
    ledger=rows(ROOT/'candidate_ledger.jsonl')
    for pos in range(1,6):
        inp=inputs[pos-1];out=outputs[pos-1];payload=__import__('json').loads(inp['messages'][1]['content']);ev=payload['evidence'];cid=inp['candidate_id']
        status='KEEP' if pos!=2 else 'REVIEW_REQUIRED'
        dimensions={'evidence_sufficiency':'SUFFICIENT' if pos!=2 else 'PARTIAL_SUPPORT_QUESTION_AMBIGUOUS','question_answer_fit':'PASS' if pos!=2 else 'REVIEW_REQUIRED','factual_claim_support':'AGENT_REVIEW_SUPPORTED' if pos!=2 else 'NO_FACTUAL_CLAIMS_ABSTENTION_REQUIRES_REVIEW','scope_modality_negation_quantity':'PRESERVED' if pos!=2 else 'INSUFFICIENCY_STATEMENT_TOO_BROAD','outside_details':'NONE_IDENTIFIED','abstention_justified':'NOT_APPLICABLE' if pos!=2 else 'NOT_CONFIRMED','ambiguity_conflict':'NO_MATERIAL_CONFLICT_FOR_SELECTED_ANSWER' if pos!=2 else 'MULTIPLE_POSSIBLE_READINGS'}
        audit.append({'candidate_id':cid,'position':pos,'response_sha256':out['response_sha256'],'status':status,'method':'AGENT_REVIEW','context_independence':False,'full_evidence_reviewed':True,'evidence_ids_reviewed':[e['evidence_id'] for e in ev],'dimensions':dimensions,'reason_fa':reasons[pos],'error_categories':[] if pos!=2 else ['available support overlooked','ambiguity/conflicting evidence','unresolved'],'gold_used_for_review':False,'independent_semantic_entailment':'NOT_EVALUATED'})
        claim_results=[]
        for index,cl in enumerate(out['response']['claims']):
            spans=[span(ev[ei],quote) for ei,quote in quote_specs[pos][index]]
            assert all(s['evidence_id'] in cl['evidence_ids'] for s in spans)
            claim_results.append({'claim_index':index,'claim_sha256':canonical(cl),'claim_text':cl['claim_text'],'evidence_ids':cl['evidence_ids'],'outcome':'SUPPORTED','method':'AGENT_REVIEW','reason_fa':reasons[pos],'supporting_spans':spans})
        support.append({'candidate_id':cid,'response_sha256':out['response_sha256'],'method':'AGENT_REVIEW','independent':False,'claim_results':claim_results,'abstention_review':'NOT_APPLICABLE' if pos!=2 else 'REVIEW_REQUIRED','independent_semantic_entailment':'NOT_EVALUATED'})
        ledger[pos-1].update(status=status,semantic_status='AGENT_REVIEW_COMPLETE',review_reason=None if pos!=2 else reasons[pos],semantic_method='AGENT_REVIEW',handoff_ready=False)
    save(ROOT/'audit.jsonl',audit,True);save(ROOT/'support.jsonl',support,True);save(ROOT/'candidate_ledger.jsonl',ledger,True)
    save(ROOT/'review_queue.jsonl',[r for r in audit if r['status']=='REVIEW_REQUIRED'],True)
    save(ROOT/'repairs.jsonl',[],True)
    h=save(ROOT/'checkpoints/semantic_001_005/audit.jsonl',audit,True)
    save(ROOT/'checkpoints/semantic_001_005/checkpoint.json',{'run_id':'recovery_final_v1','source_commit':'ebfadb00263a18af5dbd53931f18b434a7c7acb1','phase':'C_SEMANTIC_IN_PROGRESS','positions_completed':[1,5],'semantic_completed':5,'kept':4,'repaired':0,'valid_abstention':0,'review_required_reviewed':1,'pending_semantic':1144,'audit_sha256':h,'support_sha256':sha((ROOT/'support.jsonl').read_bytes()),'next_position':6,'next_step':'Read full question, all 10 evidence texts, answer and claims for position 6. Do not treat pending entries as semantic failures or PASS.'})
    print('Semantic batch 001–005: 4 KEEP, 1 REVIEW_REQUIRED; files saved and reloaded.')

if __name__=='__main__':main()
