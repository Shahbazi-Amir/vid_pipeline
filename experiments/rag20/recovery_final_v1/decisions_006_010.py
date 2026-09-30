"""Explicit decisions from reading all evidence for positions 6–10."""
import copy
import json
from audit_structure import ROOT,rows,canonical,sha
from incremental_review import verify_current,append_decisions,publish

def decision(pos, reason, specs, repair=None, dimensions=None, units=None):
    inp=rows(ROOT/'inputs.jsonl')[pos-1];out=rows(ROOT/'outputs.jsonl')[pos-1]
    payload=json.loads(inp['messages'][1]['content']);ev=payload['evidence']
    response=copy.deepcopy(repair or out['response']);h=canonical(response);rev=1 if repair else 0
    dims=dict(evidence_sufficiency='SUFFICIENT_FOR_BOUNDED_ANSWER',question_answer_fit='PASS',
              factual_claim_support='AGENT_REVIEW_SUPPORTED',scope_modality_negation_quantity='PRESERVED',
              outside_details='NONE_IDENTIFIED',abstention_justified='NOT_APPLICABLE',
              ambiguity_conflict='NO_MATERIAL_CONFLICT_FOR_BOUNDED_ANSWER')
    dims.update(dimensions or {})
    audit=dict(schema_version=2,candidate_id=inp['candidate_id'],position=pos,revision=rev,
               response_sha256=h,status='REPAIRED' if repair else 'KEEP',method='AGENT_REVIEW',
               context_independence=False,full_evidence_reviewed=True,
               evidence_ids_reviewed=[e['evidence_id'] for e in ev],
               evidence_text_hashes=[sha(e['text'].encode()) for e in ev],
               dimensions=dims,reason_fa=reason,error_categories=['missing factual claim coverage'] if repair else [],
               gold_used_for_review=False,answer_factual_coverage_reviewed=True,
               independent_semantic_entailment='NOT_EVALUATED')
    results=[]
    assert len(specs)==len(response['claims'])
    for k,(cl,items) in enumerate(zip(response['claims'],specs)):
        spans=[]
        for ei,quote,why in items:
            e=ev[ei];start=e['text'].index(quote)
            spans.append(dict(evidence_id=e['evidence_id'],start=start,end=start+len(quote),
                              quote=quote,unit='UNICODE_CODE_POINT',semantic_reason_fa=why))
        results.append(dict(claim_index=k,claim_sha256=canonical(cl),claim_text=cl['claim_text'],
                            evidence_ids=cl['evidence_ids'],outcome='SUPPORTED',method='AGENT_REVIEW',
                            reason_fa='؛ '.join(i[2] for i in items),supporting_spans=spans))
    support=dict(schema_version=2,candidate_id=inp['candidate_id'],response_sha256=h,revision=rev,
                 method='AGENT_REVIEW',independent=False,claim_results=results,
                 answer_units=units or [dict(text=response['answer_text'],kind='FACTUAL',
                       claim_indices=list(range(len(results))),reason_fa=reason)],
                 abstention_review='NOT_APPLICABLE',independent_semantic_entailment='NOT_EVALUATED')
    result=dict(audit=audit,support=support)
    if repair:
        result['repair']=dict(candidate_id=inp['candidate_id'],position=pos,revision=1,
            original_response=out['response'],original_response_sha256=out['response_sha256'],
            previous_response_sha256=out['response_sha256'],revised_response=response,
            revised_response_sha256=h,reason_fa='بخش «نیاز زندگی بهتر» در answer_text بود اما factual claim نداشت؛ claim متناظر افزوده شد. متن پاسخ تغییر نکرد.',
            method='AGENT_REVIEW',gold_used=False,rechecked=True,recheck_reason_fa=reason)
    return result

def decisions():
    outs=rows(ROOT/'outputs.jsonl');ins=rows(ROOT/'inputs.jsonl')
    r=copy.deepcopy(outs[5]['response']);ev=json.loads(ins[5]['messages'][1]['content'])['evidence']
    r['claims'].append(dict(claim_text='متن ارائه‌شده سواد مالی را یکی از نیازهای زندگی بهتر در دوران معاصر می‌داند.',claim_type='FACTUAL',evidence_ids=[ev[0]['evidence_id']]))
    d6=decision(6,'پرسش کلی است؛ پاسخ با قید «طبق متن» جایگاه سواد مالی را در مجموعه یازده مهارت و نیاز زندگی بهتر گزارش می‌کند. برتری مطلق یا تأیید بیرونی یونسکو ادعا نشده؛ هر دو گزاره در جمله آغازین شاهد اول هستند. شواهد اهمیت و مهارت تصمیم مالی را نیز توضیح می‌دهند. پس از افزودن claim دوم، تمام محتوای واقعی پاسخ دوباره با شاهد تطبیق شد.',[
      [(0,'سواد مالی یکی از نیازهای زندگی بهتر در دوران معاصر و از مجموعه یازده مهارت زندگی مورد تأکید یونسکو است','عبارت مجموعه یازده مهارت و تأکید یونسکو صریح است؛ گزارش متن، نه صحت‌سنجی انتساب بیرونی.')],
      [(0,'سواد مالی یکی از نیازهای زندگی بهتر در دوران معاصر','این بند دقیقاً نیاز زندگی بهتر در عصر معاصر را برای سواد مالی بیان می‌کند.')]],repair=r,
      dimensions={'ambiguity_conflict':'QUESTION_BROAD_TEXT_ATTRIBUTION_PRESERVED'})
    d7=decision(7,'شاهد اول همان مقایسه ده انسان و دو سگ را با کمیت‌ها و یک سفره/یک مردار بیان می‌کند و بلافاصله قناعت و آزمندی را شرح می‌دهد. پاسخ ستیزه را به همه انسان‌ها یا رفتار واقعی همه سگ‌ها تعمیم نمی‌دهد؛ تفسیر قناعت و آزمندی از ادامه همان حکایت است.',[
      [(0,'ده انسان بر سفره‌ای غذا می‌خورند و سیر می‌شوند، اما دو سگ بر سر یک مردار، با هم ستیزه می‌کنند.','کمیت ده و دو و تقابل سیری با ستیزه هر دو در یک جمله است.')],
      [(0,'آزمند با داشتن یک جهان نعمت، همیشه گرسنه است؛ حال آنکه انسان قانع با تکه نانی سیر می‌شود.','این تقابل در ادامه حکایت دلیل تفسیر قناعت و آزمندی در پاسخ است.')]])
    answer=outs[7]['response']['answer_text'];cut=answer.index('اما ')
    d8=decision(8,'تمام شواهد گروه‌های مختلف را پوشش می‌دهند، اما معیار مشترک برای رتبه‌بندی اثر همه گروه‌ها نمی‌دهند. شاهد اول و پنجم اثر زنان بر خانواده/نسل و شاهد دوم رشد و مدیریت مالی کودکان را تصریح می‌کنند. مطالعه دانشجویان در شاهد هشتم درباره یک جمعیت و کاربردی‌بودن آموزش است؛ از آن برتری قطعی زنان یا کودکان نتیجه نمی‌شود. پاسخ حمایت موجود را ارائه می‌کند و بخش «بیشتر از همه» را محدود می‌گذارد.',[
      [(0,'و زنان چون آموزش آنها معمولاً اثر گسترده‌ای بر خانواده و نسل بعد می‌گذارد.','اثر گسترده معمول آموزش زنان بر خانواده و نسل بعد ذکر شده است.'),
       (4,'در بسیاری از برنامه‌های آموزشی هم زنان یکی از گروه‌های مهم هدف‌اند، چون نقش آنها در خانواده و انتقال رفتار به فرزندان بسیار پررنگ است.','نقش انتقال رفتار به فرزند و اهمیت گروه هدف، همان علت اهمیت ویژه در claim است.')],
      [(1,'شروع این آموزش‌ها از سنین کم و در کودکی اهمیت بسیاری دارد. آشنایی کودکان با مفاهیم سواد مالی تأثیر فوق‌العاده‌ای بر رشد شخصیت آن‌ها می‌گذارد. کودکان هر چه زودتر با پول، ارزش آن، پس‌انداز، تفاوت نیاز و خواسته و سرمایه‌گذاری آشنا شوند، در آینده مدیران مالی بهتری برای خود و خانواده‌شان خواهند بود.','شروع زودهنگام، رشد و مدیریت مالی آینده هر سه در این span است.')]],
      dimensions={'evidence_sufficiency':'PARTIAL_FOR_SUPERLATIVE_SUFFICIENT_FOR_BOUNDED_ANSWER',
                  'question_answer_fit':'BOUNDED_ANSWER_COMPARATIVE_LIMIT_EXPLAINED',
                  'ambiguity_conflict':'OUTCOME_AND_COMPARISON_METRIC_UNSPECIFIED'},
      units=[dict(text=answer[:cut],kind='FACTUAL',claim_indices=[0,1],reason_fa='اهمیت زنان و کودکان با دو claim پوشش داده شده.'),
             dict(text=answer[cut:],kind='EVIDENCE_LIMITATION',claim_indices=[],reason_fa='پس از خواندن همه ده شاهد، مقایسه یکسان همه گروه‌ها در داده ارائه‌شده وجود ندارد؛ این محدودیت شواهد است، نه ادعای نبود پژوهش در جهان.')])
    d9=decision(9,'پرسش پیش‌فرض منفی دارد. شاهد سوم ابتدا تصور «مهارت خاص نمی‌خواهد» را مطرح و سپس آن را با تخصص حرفه‌ای و مهارت رانندگی و تعامل رد می‌کند. پاسخ نفی نقل‌شده را به موضع گوینده تبدیل نمی‌کند. بقیه شواهد ضرورت رانندگی درست و تفاوت با تحصیل دانشگاهی را نقض نمی‌کنند.',[
      [(2,'به نظر من رانندگی تخصصه','رانندگی به صراحت تخصص نامیده شده؛ مقدمات پاسخ درباره رد تصور بی‌مهارتی با این عبارت و ادامه متن توجیه می‌شود.'),
       (2,'یک نفر تاکسی داشته باشه یک مهارتی داره چه در تعامل با مسافرها چه مهارتهای رانندگی','هر دو مهارت تعامل با مسافر و رانندگی ذکر شده؛ دامنه رانندگی حرفه‌ای در claim حفظ است.')]],
      dimensions={'question_answer_fit':'FALSE_PREMISE_CORRECTED_WITH_EVIDENCE'})
    d10=decision(10,'شاهد اول اختیار برخوردار در مصرف‌نکردن و بخشش را از نداشتن جدا می‌کند؛ شاهد دوم تولید بالا و مصرف متعادل را مطرح می‌کند. شاهد پنجم هم توان برخورداری و گذشت آگاهانه را تصریح می‌کند. پاسخ با قید «در این شواهد» این برداشت را گزارش می‌کند؛ فقر اجباری را زهد نمی‌نامد و احکام یا انتساب تاریخی تازه نمی‌افزاید.',[
      [(0,'کسی که اصلا پولی نداره که نمی‌تونه زاهد باشه\nاون اصلا نداره\nکسی که داره و خودش مصرف نمی کنه به دیگران می‌ده اون زاهده','تقابل نداشتن با داشتن و بخشیدن، عنصر انتخاب فرد برخوردار را مستقیم پشتیبانی می‌کند.'),
       (1,'«تولید ثروت بالا، مصرف شخصی متعادل و مسئولانه.» زهد به معنی تنبلی یا ناتوانی در تولید نیست؛ بیشتر به نوع وابستگی و مصرف مربوط است.','مصرف شخصی متعادل در کنار توان تولید دلیل محدودکردن مصرف است؛ پاسخ ناتوانی از داشتن را فضیلت معرفی نمی‌کند.')]])
    return [d6,d7,d8,d9,d10]

if __name__=='__main__':
    current,state=verify_current(restore=True)
    state=append_decisions(state,decisions())
    publish(state,'semantic_006_010_v2',[6,10],
            'این نوبت ۵ مورد جدید و یک اصلاح claim انجام شد؛ ادامه در همین نوبت از ۱۱. مورد ۲ همچنان review است.',
            '2026-09-30T23:12:00+00:00')
