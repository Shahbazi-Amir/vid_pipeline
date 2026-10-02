# بستهٔ تجمیع ممیزی — ۲ اکتبر ۲۰۲۶

بررسی‌شده: 796 از ۱۱۴۹؛ باقی‌مانده: 353.

این بسته خروجی میانی ممیزی AGENT_REVIEW است؛ اجرای Qwen، تأیید انسانی مستقل یا خروجی آمادهٔ NB19/NB20 نیست.

## خروجی یکپارچه

merged/reviewed_inputs.jsonl سؤال و تمام evidenceهای موارد بررسی‌شده را دارد.
merged/reviewed_outputs.jsonl پاسخ فعال همان موارد، پس از اعمال اصلاحات معتبر، را دارد.
merged/audit.jsonl و support.jsonl گزارش تمام claimها، spanها و پوشش متن پاسخ را نگه می‌دارند.
merged/repairs.jsonl تاریخچهٔ اصلاحات را حفظ می‌کند.
merged/review_queue.jsonl موارد بررسی‌شدهٔ نیازمند review نهایی را دارد؛ این‌ها با موارد بررسی‌نشده یکی نیستند.
merged/candidate_ledger.jsonl رجیستری واحد ۱۱۴۹ شناسه با وضعیت فعال است.
MANIFEST، acceptance_receipts و validation مبنای snapshotها، hashها و اعتبارسنجی را ثبت می‌کنند.

## ادامه در همین چت

محدوده‌های بررسی‌نشده: [[315, 393], [427, 427], [661, 771], [988, 1149]].
شناسهٔ دقیق هر مورد در remaining_candidates.json و CSV ثبت است.
resume_batches_25.json صف ثابت گروه‌های ۲۵تایی است؛ هر گروه می‌تواند متناسب با ظرفیت نوبت کوچک‌تر شود.
از اولین مورد واقعاً بررسی‌نشده ادامه بده؛ فقط سؤال، تمام evidenceها، پاسخ، تمام claimها، اصلاح ضروری و بازبینی اصلاحات.
Gold، expected_answer و API مدل ممنوع‌اند. RAG_finance فقط خواندنی است.
پیشرفت جدید باید در checkpoint نام‌جدید ثبت شود؛ snapshotهای قبلی بازنویسی نشوند.
چت‌های قبلی به snapshotهای pinned بسته شده‌اند؛ ثبت جدید احتمالی آنان فقط پس از بررسی اختلاف و حذف تکرار قابل افزودن است.
هیچ ادعای اجرای پس‌زمینه یا توقف فنی چت‌های دیگر در این بسته وجود ندارد.

## کار تکمیلی باقی‌مانده

45 مورد بررسی‌شده نیازمند review؛ پنج مورد قدیمی positions 1–5 نیازمند تکمیل قرارداد پوشش متن پاسخ نسخهٔ ۲.
source/location، adapter واقعی NB19 و handoff NB20 هنوز NOT_RUN هستند.
فایل audit در batch_0030 ممیز ۲ در GitHub خراب است؛ position 427 از شمار پذیرفته‌شده خارج شده و در صف ادامه است. raw آن حفظ شده و جزئیات در QUARANTINE.json آمده‌اند. سایر رکوردهای ممیز ۲ جداگانه با همان schema و validator موجود بررسی شده‌اند؛ کل CURRENT ممیز ۲ PASS اعلام نمی‌شود.
کیفیت معنایی از گزارش‌های AGENT_REVIEW حفظ شده؛ هماهنگ‌کننده ساختار، schema، revision/hash، span، lineage و پوشش assignment را اعتبارسنجی کرده است و ممیزی مستقل دوبارهٔ تمام محتوا انجام نداده است.

## بازیابی

شاخه‌ها و commit دقیق هر ممیز در merged/acceptance_receipts.json ثبت شده‌اند.
workers/ فقط batchهای referenced و CURRENT همان snapshotهای معتبر را نگه می‌دارد.
resume_tools/ ابزار موجود، قراردادها، assignmentها و baseline ۱۵تایی را برای بازیابی دارد.
منابع ثابت کامل inputs/outputs در resume_tools موجودند؛ منابع Gold در این بسته وارد نشده‌اند.
پس از استخراج، ابزار range_io.py را در ساختار همان resume_tools با --directory به workers/auditor_N وصل کن؛ ممیز ۲ تا رفع ناسازگاری batch_0030 در verify کامل شکست می‌خورد. این ایراد پنهان یا با تغییر hash تاریخی رفع نشده است.
فایل‌های یکپارچه خودشان با validator موجود incremental_review.validate قابل بررسی‌اند.
