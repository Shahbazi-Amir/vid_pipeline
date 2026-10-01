تو ممیز 2 پروژهٔ vid_pipeline هستی. این چت اجرایی فقط مالک positions 394–771 است؛ ۳۷۸ candidate. هدف همان ممیزی کامل و اصلاح انتخابی است، با حفظ کیفیت و بدون نیاز به تأیید کاربر بعد از هر batch. خودت چت یا sub-agent دیگری ایجاد نکن و اجرای پس‌زمینه پس از پایان پاسخ را ادعا نکن.

## منابع ثابت و مالکیت دقیق

repository: Shahbazi-Amir/vid_pipeline
branch اختصاصیِ از قبل ساخته‌شده: agent/rag20-auditor-2-v1
commit شروع مشترک سه ممیز: ccc75605721077b209027fee65d4ea98895ed8fb
commit تولید ورودی/پاسخ اصلی: ebfadb00263a18af5dbd53931f18b434a7c7acb1
checkpoint معتبر ممیزی مرکزی: commit 6b3566de8b6e103508090a1807d4c893e2f5fecc، ۱۵ مورد؛ مسیر checkpoints/semantic_006_015_verified_v2 در recovery_final_v1.
assignment: experiments/rag20/recovery_final_v1/parallel_v1/assignments/auditor_2.json
SHA256 assignment: 000f866a2035949d689a9a7a68e80b626415564fdf708f1c3144f6d2573b6039
مسیر یگانهٔ نوشتن:
experiments/rag20/recovery_final_v1/parallel_v1/workers/auditor_2/

assignment را دقیقاً از commit شروع مشترک بخوان:
https://github.com/Shahbazi-Amir/vid_pipeline/blob/ccc75605721077b209027fee65d4ea98895ed8fb/experiments/rag20/recovery_final_v1/parallel_v1/assignments/auditor_2.json

position یک‌مبنایی و مطابق ترتیب ثابت inputs.jsonl snapshot است. بر اساس candidate ID یا سؤال مرتب نکن. candidate ID، messages_sha256، original_response_sha256، revision اصلی و مسیر ورودی/خروجی دقیق هر مورد در assignment ثبت است. فقط همان ۳۷۸ شناسه را پردازش کن؛ تغییر محدوده یا واگذاری یک candidate به ممیز دیگر ممنوع است. ۱۵ مورد اول و پنج تکمیل قدیمی مربوط به هماهنگ‌کننده‌اند.

## شروع و دریافت منابع؛ بدون از دست‌دادن پیشرفت

۱. branch اختصاصی را واقعاً از GitHub بخوان. اگر از commit شروع جلوتر رفته، آخرین CURRENT.json و checkpoint معتبر خودش را بررسی و از اولین candidate واقعاً بررسی‌نشده ادامه بده؛ branch یا فایل‌ها را به commit شروع reset نکن. ancestry و assignment/tool hashes باید ثابت بمانند.
۲. یک checkout/worktree جدا برای همین ممیز در workspace خودت داشته باش؛ روی checkout مشترکِ قابل‌نوشتن با ممیز دیگری کار نکن. اگر Git محلی در دسترس است، branch موجود را fetch/checkout کن؛ force-push یا reset ممنوع است. با connector GitHub هم می‌توان فایل‌های pinned را دقیقاً materialize و commit کرد. فایل موجود در workspace با ثبت در GitHub یکسان نیست.
۳. از commit شروع، PLAN.json، assignment خودت، shared/range_io.py، shared/decision.schema.json، shared/DECISION_CONTRACT_FA.md و فایل‌های frozen_files در PLAN را دریافت کن. همه زیر experiments/rag20/recovery_final_v1 هستند. baseline snapshot فقط خواندنی است و ابزار آن را در حافظه استفاده می‌کند؛ هیچ ledger کامل تازه‌ای نساز.
۴. DEPENDENCIES.json موجود روش و ۲۶ فایل ثابت inputs/outputs اصلی و SHA256 و Git blob SHA را مشخص کرده است. آن فایل‌ها را از commit تولید ذکرشده، در repository_path دقیق همان manifest تأمین کن. inputs شامل تمام متن evidenceهای لازم است؛ رجیستری حجیم یا Gold برای این ادامه لازم نیست. اگر دریافت content خالی/ناقص است، blob همان SHA را با connector بخوان و با hash مطابقت بده؛ ناقص را معتبر فرض نکن.
۵. اگر aggregateهای ورودی/خروجی در workspace موجود و hash مطابق PLAN دارند، فقط آن‌ها را بخوان. اگر موجود نیستند، با ابزار مشترک زیر فقط در source_cache مسیر اختصاصی خودت بازسازی کن؛ فایل outputs.jsonl هماهنگ‌کننده را ایجاد/ویرایش نکن:

```bash
python experiments/rag20/recovery_final_v1/parallel_v1/shared/range_io.py rebuild-sources --worker auditor_2
python experiments/rag20/recovery_final_v1/parallel_v1/shared/range_io.py verify --worker auditor_2
```

rebuild-sources فقط ورودی/خروجی‌های ثابت را از ۲۶ فایل pinned دوباره تجمیع می‌کند؛ source_cache قدیمیِ هماهنگ‌کننده و Gold را نمی‌خواند و تصمیم ممیزی تولید نمی‌کند. cache در ZIP تکرار نشود. اگر دسترسی نوشتن GitHub نیست، ممیزیِ قابل‌انجام و checkpoint محلی را ادامه بده و صریح بگو کدام commit ثبت نشده؛ ادعای ثبت مخزن نکن.

## کیفیت بررسی؛ بدون کاهش پوشش

برای هر candidate، سؤال، تمام evidenceها با متن کامل، پاسخ فعال و همهٔ claims را واقعاً بخوان. evidence ID و متن و hash را با ورودی pinned همان position تطبیق بده. اگر ابزار truncate کرد، باقی متن را با بخش‌بندی کوچک‌تر بخوان؛ excerpt، keyword search، شباهت لفظی یا فقط offset جای خواندن کامل و قضاوت معنایی را نمی‌گیرد. از شروع تا پایان هر evidence را بخوان؛ پایان متن خود chunk با حذف خروجی ابزار اشتباه نشود.

جدا ارزیابی و ثبت کن: کفایت evidence؛ پاسخ مستقیم به سؤال؛ حمایت هر factual claim؛ حفظ دامنه و قید و نفی و کمیت؛ نبود جزئیات بی‌شاهد؛ موجه‌بودن abstention؛ ابهام و تعارض. قیدهای «طبق متن»، «ممکن است»، گروه/زمان و کمیت‌ها حفظ شوند. هر factual claim در answer_text باید با claims و support پوشش داشته باشد؛ فقط بررسی فهرست claims کافی نیست.

روش AGENT_REVIEW است؛ verifier مستقل یا تأیید انسانی نیست. method و context_independence/independent مطابق schema ثبت شوند. independent_semantic_entailment=NOT_EVALUATED؛ Gold، expected_answer، برچسب پاسخ مرجع و quoteهای Gold را نخوان و وارد تولید/اصلاح نکن. نام golden_v2_candidate در ID، مجوز استفاده از Gold نیست. هیچ API مدل/ارائه‌دهنده‌ای فراخوانی نکن و این خروجی را اجرای Qwen معرفی نکن. هیچ تغییری در RAG_finance مجاز نیست؛ notebookها را اجرا/import نکن.

پاسخ درست را KEEP کن؛ صرفاً برای سبک بازنویسی نکن. نقص روشن که با evidence قابل‌اصلاح است، در همان زیرگروه اصلاح و نسخهٔ جدید را دوباره بررسی کن. original response و hash محفوظ؛ revision جدید با previous_response_sha256؛ audit/support مربوط به پاسخ فعال و hash یکسان. اگر گزارهٔ واقعی در متن پاسخ جا مانده ولی claim ندارد، تکمیل claims با همان متن پاسخ درست مجاز است و revision ثبت می‌شود. ابهام یا evidence ناکافی را با حدس رفع نکن؛ REVIEW_REQUIRED یا VALID_ABSTENTION با دلیل دقیق. مورد دشوار نباید بقیه محدوده را متوقف کند.

## قرارداد آماده و ذخیرهٔ incremental محدوده

ابزارها را دوباره نساز؛ ابزار مرکزی و shared را تغییر نده و ممیزی ساختاری همه ۱۱۴۹ مورد را تکرار نکن. shared/DECISION_CONTRACT_FA.md و decision.schema.json قرارداد کامل آماده‌اند؛ range_io.py همان incremental_review validator/merge موجود را در حافظه به delta محدوده متصل می‌کند. examples مرکزیِ ۶–۱۵ فقط الگوی ساختارند، نه تصمیم ثابت برای candidate جدید.

در مسیر اختصاصی خودت decisions_working.jsonl بساز: هر خط envelope با audit، support و فقط در صورت اصلاح repair. تمام فیلدهای required schema لازم‌اند. هیچ رکورد بررسی‌نشده با KEEP یا SUPPORTED ننویس.

- audit.schema_version=2؛ revision=0 برای پاسخ اصلی و ۱، ۲، ... برای اصلاح؛ candidate_id و position دقیق assignment؛ response_sha256 مطابق پاسخ فعال. evidence_ids_reviewed و evidence_text_hashes تمام شواهد به ترتیب ورودی. dimensions هفت‌گانه و reason_fa موردی؛ full_evidence_reviewed/answer_factual_coverage_reviewed فقط پس از بررسی واقعی true.
- support.claim_results برای تک‌تک claims فعال، به همان ترتیب؛ quote/span واقعی با evidence_id و start/end در واحد UNICODE_CODE_POINT و semantic_reason_fa که entailment دامنه کامل ادعا را توضیح دهد. quote نزدیک به موضوع کافی نیست.
- support.answer_units متن پاسخ فعال را کامل، بدون حذف، به بندها تقسیم می‌کند؛ اتصال text آن‌ها دقیقاً answer_text باشد. گزاره‌های واقعی به claim_indices وصل شوند؛ واقعیت را برای عبور از validator INTERPRETIVE برچسب نزن. نوع واحد و دلیل در قرارداد آمده است.
- repair پاسخ اصلی و revised_response، hashهای اصلی/قبلی/جدید، revision و علت و rechecked=true با دلیل بازبینی واقعی را ثبت می‌کند. نتیجهٔ اصلاح قبل از ذخیره باید دوباره با تمام evidence و claims فعال بررسی شود.
- KEEP/REPAIRED فقط با حمایت کامل claims؛ REVIEW_REQUIRED بررسی‌شده اما هنوز حل‌نشده؛ VALID_ABSTENTION با claims خالی و abstention_justified=JUSTIFIED.

با import از audit_structure، canonical(value) هش canonical پاسخ/claim و sha(bytes) هش فایل را محاسبه کن. این محاسبه و تولید offset تنها کار مکانیکی است، تصمیم معنایی باید اختصاصی و حاصل خواندن واقعی باشد.

در زیرگروه‌های ۵ تا ۱۰تایی کار کن. هدف نوبت ۵۰ candidate جدید است؛ اگر ظرفیت واقعی اجازه داد ادامه بده. اگر محدودیت واقعی خواندن کامل/ابزار/context رسید، تعداد را کاهش بده و علت دقیق و نقطهٔ ادامه را ثبت کن؛ کیفیت را کم نکن. برای ذخیرهٔ اولین زیرگروه از batch_0001 و برای ادامه از شمارهٔ بعد از CURRENT خودت استفاده کن:

```bash
python experiments/rag20/recovery_final_v1/parallel_v1/shared/range_io.py commit-batch --worker auditor_2 --decisions experiments/rag20/recovery_final_v1/parallel_v1/workers/auditor_2/decisions_working.jsonl --batch batch_0001
python experiments/rag20/recovery_final_v1/parallel_v1/shared/range_io.py verify --worker auditor_2
```

بعد از نخستین batch شماره را بر اساس CURRENT تغییر بده؛ تصمیم‌های قدیمی را دوباره وارد draft نکن، مگر replay دقیق یا revision واقعی. اجرای تکراری یک envelope یکسان no-op است؛ تعارض بدون revision رد می‌شود. برای هر batch فقط audit/support/repairs/ledger/review_queue همان batch و validation کوچک، زیر batches/batch_NNNN ذخیره می‌شوند؛ ledger تمام ۱۱۴۹ مورد کپی نمی‌شود. CURRENT اختصاصی فقط batch refs/hashes، شناسه‌های یکتا و next_position را نگه می‌دارد. قبلی‌ها immutable هستند و بازنویسی نمی‌شوند.

ذخیره ابتدا staging، validation و reload، سپس pointer نهایی است. اگر قطع اتصال شد: CURRENT معتبر authoritative است؛ staging یا batch unreferenced را بررسی‌شده حساب نکن. اگر batch نهایی یا CURRENT.pending.json وجود دارد اما pointer ثبت نشده، فقط در مسیر خودت دستور زیر را اجرا کن؛ ابزار پیش از publication دوباره hash/schema/lineage را کنترل می‌کند:

```bash
python experiments/rag20/recovery_final_v1/parallel_v1/shared/range_io.py recover-pending --worker auditor_2
```

اگر staging ناقص مانده، آن را بدون حذف پیشرفت قبلی در مسیر خودت quarantine کن؛ بازنویسی batch معتبر ممنوع است. هیچ CURRENT یا ledger یا outputs مرکزی و هیچ مسیر ممیز دیگری را تغییر نده. shared helper، assignments و frozen files فقط خواندنی‌اند. فقط output_path خودت را stage/commit کن.

## checkpoint، GitHub، گزارش و پایان نوبت

پس از هر ۱۰ candidate جدید کامل، checkpointهای کوچک را در branch اختصاصی خودت commit کن؛ در پایان زودتر نوبت هم آخرین checkpoint معتبر را commit کن. commit کامل و hashهای فایل‌ها را بازخوانی و تطبیق بده. از GitHub connector یا Git معمولیِ مجاز استفاده کن؛ force-push و overwrite ممنوع است. برای هر revision، history پیشین محفوظ بماند.

بعد از checkpoint یا حدود پنج دقیقه، هرکدام زودتر و در محیط ممکن بود، گزارش کوتاه بده: «ممیز 2؛ بررسی‌شده X/378؛ این نوبت Y؛ باقی‌مانده W؛ checkpoint ...؛ commit ...؛ ادامه از position ...». count از candidateهای یکتا در CURRENT معتبر خودت باشد، نه تعداد revision/ادعا یا جمع پیام‌ها. متن evidenceها را برای کاربر بازنشر نکن؛ بدون نیاز به تأیید کاربر زیرگروه بعدی را ادامه بده.

تنها در پایان نوبت یا تحویل محدوده یک ZIP نسخه‌دارِ کوچک بساز: CURRENT، batchهای referenced، PROGRESS_FA، HANDOFF/provenance با branch، commit کامل، run_id، assignment/source/tool hashes و روش دریافت منابع. منابع حجیم ثابت، ledger مرکزی ۱۱۴۹ مورد و ZIP کامل مرکزی را تکرار نکن. SHA256 بسته و لینک دانلود واقعی بده؛ این checkpoint میانی است، خروجی نهایی NB19/NB20 نیست. نوبت بعد از اولین candidate بررسی‌نشدهٔ CURRENT ادامه می‌یابد؛ اجرای خودکار پس از پاسخ ادعا نشود.

HANDOFF.json در مسیر خودت شامل owner، branch، common_start_commit، assignment_sha256، آخرین commit بررسی‌شدهٔ داده، مسیر و hash CURRENT، تعداد یکتا و statusها، candidate IDs و revision/hash فعال یا refs قابل‌تأمین آن‌ها، پوشش/باقی‌مانده، blockerها و next_position باشد. Git commit خود HANDOFF می‌تواند commit بعدی باشد؛ self-referential hash/commit جعل نکن.

برای پذیرش، هماهنگ‌کننده فقط فایل/commit قابل‌اثبات را می‌خواند؛ schema، assignment، revision/hash، span، پوشش factual پاسخ و نبود شناسه خارج از محدوده را کنترل می‌کند و از اجتماع IDs شمار مرکزی می‌سازد. خودت هیچ فایل نهایی مشترکی را merge نکن. وقتی همه ۳۷۸ مورد واقعاً بررسی شدند، assignment_complete مجاز است؛ import-ready هنوز false می‌ماند. source/location مستقل، رفع reviewهای سراسری، adapter واقعی NB19، validation نهایی و handoff NB20 کار هماهنگ‌کننده‌اند و انجام‌نشده را PASS نکن.

اکنون branch و آخرین checkpoint خودت را بررسی، منابع pinned را تأمین و از اولین position بررسی‌نشدهٔ assignment خودت واقعاً شروع کن؛ فقط اعلام آمادگی نکن.
