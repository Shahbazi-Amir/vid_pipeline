# پذیرش و تجمیع؛ فقط توسط هماهنگ‌کننده

مبنای تقسیم، snapshot تولید ebfadb00263a18af5dbd53931f18b434a7c7acb1 و ترتیب
۱۱۴۹ ورودی ثابت است. مبنای ممیزی ۱۵ مورد، commit
6b3566de8b6e103508090a1807d4c893e2f5fecc است. جزئیات کامل در PLAN.json.
شاخه‌های ممیزها از یک commit آماده‌سازی مشترک ساخته می‌شوند؛ SHA دقیق در
BRANCH_STARTS.json ثبت می‌شود. assignmentها و OWNERSHIP.jsonl مالک هر شناسه را تعیین می‌کنند.

## پیش از پذیرش هر تحویل

۱. branch و commit کاملِ اعلام‌شده را از GitHub واقعاً بخوان. ادعای پیام، فایل محلی بدون
ثبت مخزن یا ZIP بدون provenance، پیشرفت مرکزی نیست. رابطهٔ ancestry با commit شروع
مشترک را کنترل کن. فایل‌ها را از همان SHA، نه head متغیر شاخه، دریافت کن.

۲. tree/diff commit شروع و تحویل را مقایسه کن: هر تغییر باید زیر output_path همان
ممیز باشد. تغییر shared، assignments، فایل‌های مرکزی، batchهای اصلی یا خروجی دیگر
ممیزان باعث توقف پذیرش آن تحویل می‌شود. هیچ force-push، reset، حذف یا overwrite
پیشرفت پذیرفته‌شده مجاز نیست. از وضعیت قبلی معتبر ادامه بده؛ اختلاف را گزارش کن.

۳. CURRENT.json محدوده و تمام checkpointها و فایل‌های referenced را در مسیر جداگانهٔ
موقت هماهنگ‌کننده materialize کن. Git blob SHAها را با tree همان commit و SHA256ها را
با CURRENT/checkpoint تطبیق بده. orphan یا staging یا batch خارج از CURRENT شمارش نشود.
schema، run_id، owner و assignment_sha256 باید دقیقاً به قرارداد ثبت‌شده وصل باشند.

۴. از ابزار مشترک، در حالت verify و مسیر فقط‌خواندنیِ تحویل استفاده کن:

```bash
python experiments/rag20/recovery_final_v1/parallel_v1/shared/range_io.py verify --worker auditor_1 --directory /absolute/path/to/materialized/auditor_1
```

برای ممیز ۲ و ۳ worker را عوض کن. fixed sources طبق DEPENDENCIES باید در دسترس باشند.
این دستور فایل مرکزی یا محدوده را نمی‌نویسد. candidate خارج از assignment، position
نادرست، duplicate در batch، حذف سابقه، revision/hash ناسازگار، claim بررسی‌نشده یا span
نادرست مردود است. پوشش جزئی مجاز است اما assignment_complete تنها برای ۳۷۸ شناسهٔ
واقعاً بررسی‌شده true می‌شود. source/location، adapter و handoff انجام‌نشده PASS نمی‌شوند.

۵. برای هر تحویل پذیرفته‌شده یک receipt مستقل زیر coordinator/receipts/ ثبت کن:
branch، commit کامل، common_start_commit، owner، assignment hash، CURRENT file SHA256،
blob/hash فایل‌های خوانده‌شده، فهرست candidate_id و revision/hash فعال، نتیجه validation
و زمان واقعی پذیرش. پذیرش snapshot جدید باید تمام batchهای قبلاً پذیرفته‌شدهٔ همان ممیز
را با همان hash حفظ کند. یک شناسه با مالک دیگر رد می‌شود؛ replay همان revision/hash
no-op است؛ revision جدید باید lineage قابل‌اثبات داشته باشد. اختلاف نسخه حل‌نشده وارد
شمار جدید یا پاسخ فعال مرکزی نشود. بررسی بودن و پذیرش معنایی از هم جدا باقی بمانند.

## شمارش و تجمیع

گزارش مرکزی فقط این فرم را داشته باشد:
«بررسی‌شده: X از ۱۱۴۹؛ باقی‌مانده: Y».

X اندازهٔ اجتماع candidate_idهای ممیزی مرکزی معتبر و receiptهای پذیرفته‌شده است؛
Y=1149-X. جمع تعداد پیام‌ها یا commitها یا revisionها ممنوع است. جایگزینی نسخهٔ یک
candidate، شمار را افزایش نمی‌دهد؛ تکمیل پوشش نسخهٔ ۲ پنج مورد قدیمی هم شمار را زیاد نمی‌کند.
برای هر owner آخرین snapshot سازگارِ پذیرفته‌شده authoritative است؛ تاریخچهٔ receiptها
حذف نشود. central PROGRESS_FA و receiptها را در commit هماهنگ‌کننده ثبت کن.

فقط هماهنگ‌کننده تصمیم‌های پذیرفته‌شده را روی state معتبر جاری مرکزی، در حافظه،
با append_decisions اعمال می‌کند؛ کار ممیزان مستقیماً cherry-pick/merge روی CURRENT
یا ledger مرکزی نمی‌شود. decisionها از audit/support/repairs هر batch ساخته می‌شوند.
replay دقیق no-op؛ تغییر پاسخ نیازمند revision بعدی با parent hash است. ممیزی تکمیلی
۱–۵ که فقط metadata پوشش پاسخ را تکمیل می‌کند، اصل پاسخ را تغییر نمی‌دهد: سابقهٔ قدیمی
در checkpoint مستقل حفظ می‌شود و نتیجهٔ تکمیلی به‌عنوان amendment مستند می‌شود؛
برای عبور از محدودیت revision، پاسخ درست را بی‌دلیل تغییر نده. این کار محدودِ مرکزی
پس از بررسی واقعی و با اصلاح ضروری حفاظت metadata انجام می‌شود و ممیزان را معطل نمی‌کند.

بعد از validate و preserve و ذخیرهٔ موقت/reload، publish مرکزی را فقط به checkpoint
نام‌جدید فراخوانی کن. hashهای audit/support/ledger فعال باید از یک پاسخ و revision باشند.
وقتی ۱۱۴۹ candidate پوشش واقعی دارند، reviewهای حل‌نشده، پوشش قدیمی، source/location،
adapter NB19، validation سراسری و handoff NB20 هنوز باید جدا تکمیل شوند؛ کامل‌شدن شمار
به‌تنهایی import-ready نیست. بدون اجرای مرحله، PASS اعلام نشود.

## ثبت و تحویل هر ممیز

زیرگروه‌های ۵ تا ۱۰تایی؛ checkpoint کوچک و commit پس از هر ۱۰ مورد جدید کامل یا پایان
زودتر نوبت. ذخیرهٔ batch شامل فقط رکوردهای جدید/نسخهٔ جدید همان محدوده است؛ بدون
کپی ledger تمام ۱۱۴۹ مورد. ZIP در پایان نوبت یا تحویل محدوده، شامل فقط CURRENT،
batchهای referenced، گزارش و provenance (branch، commit، assignment/source/tool hashes).
منابع ثابت از commit مشخص تأمین می‌شوند و در ZIP تکرار نمی‌شوند.
هماهنگ‌کننده بسته‌های قبلی را به‌دلیل ثبت تقسیم کار دوباره نمی‌سازد.
