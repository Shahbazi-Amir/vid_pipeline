# قرارداد مشترک ممیزی؛ نسخهٔ پاسخ ۲

ابزارهای مرکزی incremental_review.py، audit_structure.py و verify_recovery.py ثابت هستند.
range_io.py فقط ذخیرهٔ delta در محدودهٔ اختصاصی را به همان validator وصل می‌کند؛
این ابزار هیچ تصمیم معنایی تولید نمی‌کند و صحت معنایی را با offset اثبات نمی‌کند.
schema اجرایی decision.schema.json است. از ساختن ابزار یا قرارداد جایگزین خودداری کنید.

ورودی ذخیره‌سازی JSONL است؛ هر خط یک envelope با audit، support و در صورت اصلاح repair.
همهٔ کلیدهای audit و support در schema لازم‌اند. additionalProperties=false است؛
دلیل تفصیلی را در reason_fa و semantic_reason_fa بنویسید، نه در کلیدهای اختراعی.

- audit: candidate_id و position دقیق assignment؛ schema_version=2؛ revision=0
  برای پاسخ اصلی، و ۱، ۲، ... برای هر اصلاح واقعی. response_sha256 هش canonical پاسخ فعال است.
  method=AGENT_REVIEW؛ context_independence=false؛ gold_used_for_review=false؛
  independent_semantic_entailment=NOT_EVALUATED. full_evidence_reviewed=true و
  answer_factual_coverage_reviewed=true فقط پس از خواندن و بررسی واقعی ثبت شوند.
  evidence_ids_reviewed و evidence_text_hashes ترتیب تمام evidenceهای ورودی را حفظ می‌کنند.
- dimensions: evidence_sufficiency، question_answer_fit، factual_claim_support،
  scope_modality_negation_quantity، outside_details، abstention_justified و ambiguity_conflict
  جداگانه و مطابق همان candidate ثبت شوند. برچسب کلیِ ثابت جای دلیل موردی را نگیرد.
- status: KEEP فقط برای پاسخ اصلی درست؛ REPAIRED برای پاسخ فعالِ اصلاح و بازبینی‌شده؛
  VALID_ABSTENTION برای امتناع واقعاً موجه با claims خالی و abstention_justified=JUSTIFIED؛
  REVIEW_REQUIRED برای ابهام، تعارض یا نقص حل‌نشده، با reason_fa و error_categories غیرخالی.
  REVIEW_REQUIRED بررسی‌شده است، اما پذیرش پاسخ یا import-ready نیست.
- support: پاسخ فعال و revision و hash دقیقاً همان audit؛ independent=false؛
  برای هر claim، claim_index، claim_sha256، claim_text، evidence_ids، outcome، method،
  reason_fa و supporting_spans لازم است. ترتیب claim_results همان claims فعال است.
  outcome یکی از SUPPORTED، UNSUPPORTED، PARTIAL یا UNRESOLVED است؛ KEEP/REPAIRED
  تنها با SUPPORTED برای همهٔ claims مجاز است. REVIEW_REQUIRED می‌تواند claim حل‌نشده داشته باشد.
- span: evidence_id، quote واقعی و start/end در واحد UNICODE_CODE_POINT به‌همراه
  semantic_reason_fa لازم‌اند. توضیح دهید چرا شاهد کل دامنه، قید، نفی و کمیت claim را
  پشتیبانی می‌کند. quote تنها نزدیک موضوع یا صحیح‌بودن offset، entailment نیست.
- answer_units: بندهای پاسخ فعال را بدون حذف یا اضافه، به همان ترتیب قسمت کنید؛
  اتصال text تمام واحدها باید دقیقاً answer_text شود. هر واحد reason_fa و claim_indices
  دارد. kind یکی از FACTUAL، EVIDENCE_LIMITATION، ABSTENTION، INTERPRETIVE است.
  همهٔ گزاره‌های واقعی، حتی اگر در claims جا افتاده باشند، باید پوشش داشته باشند؛
  FACTUAL به claim متناظر وصل می‌شود. واقعیت را برای عبور از validator INTERPRETIVE
  یا EVIDENCE_LIMITATION برچسب نزنید. اگر claim واقعی جا افتاده، اصلاح انتخابیِ ساختار claims
  مجاز است؛ answer_text درست را صرفاً برای سبک تغییر ندهید.
- repair: پاسخ اصلی و original_response_sha256 محفوظ؛ previous_response_sha256 به
  آخرین revision وصل؛ revised_response و revised_response_sha256 و revision جدید؛
  reason_fa، method=AGENT_REVIEW، gold_used=false، rechecked=true و recheck_reason_fa.
  پاسخ جدید را دوباره واقعاً بررسی کنید. audit/support برای پاسخ فعال باشند.
  متن پاسخ فعال نیز با response_schema همان candidate کنترل می‌شود.

هش canonical در ابزار موجود:
`sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())`.
هش فایل، SHA256 بایت‌های واقعی فایل است و با هش canonical پاسخ یکی نیست.
برای ساخت span از quote واقعاً انتخاب‌شده، start=text.index(quote) و end=start+len(quote)
است؛ صحت ماشینی این محاسبه جای خواندن و استدلال معنایی را نمی‌گیرد.

نمونهٔ ساختار فقط‌خواندنیِ موارد ۶ تا ۱۵ در snapshot معتبر موجود است؛ تصمیم یا دلیل
آن‌ها را به سؤال‌های دیگر تعمیم ندهید. رکوردی که واقعاً بررسی نشده را ننویسید.
golden_v2_candidate در شناسه یک نام فنی است؛ مجوز دسترسی به Gold یا expected_answer نیست.
