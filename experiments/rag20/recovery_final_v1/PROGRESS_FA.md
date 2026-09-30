# وضعیت قابل‌اثبات بازیابی ممیزی

این بسته checkpoint میانی است؛ بستهٔ نهایی آمادهٔ ورود به NB19/NB20 نیست.

- snapshot تولید: `ebfadb00263a18af5dbd53931f18b434a7c7acb1` در `agent/rag-evidence-shards`.
- مرجع فقط‌خواندنی RAG_finance: `10340051b8527e9600f33c17925bb23923be20b9`.
- ۱۳ batch، ۱۱۴۹ پاسخ یکتا، پوشش کامل مجموعهٔ Test در context packets.
- ۱۱٬۴۸۰ ارجاع evidence با ترتیب و متن کامل رجیستری تطبیق داده شد؛ توزیع: ۳ مورد با ۸ شاهد، ۴ با ۹ شاهد، ۱۱۴۲ با ۱۰ شاهد.
- hash فایل‌های ورودی و خروجی با manifest، hash canonical messages و response، پرسش با صادرشدهٔ صرفاً سؤال، schema پاسخ و membership ادعاها تأیید شدند.
- ۱۵ shard رجیستری بازترکیب شدند؛ hash کل با `730aad40c0dac5c94d702f0a22aa3a891045f458a445abd087f34303bebe9fe2` تطبیق دارد.
- checkpoint ساختاری هر batch ذخیره و بازخوانی شد. آزمون‌های منفی: شناسهٔ شاهد نامعتبر، candidate تکراری، hash نادرست، span خارج از متن، quote ناسازگار و متن evidence دست‌کاری‌شده رد شدند.
- بررسی محتوایی کامل موارد ۱ تا ۵ انجام شد: ۴ KEEP، یک REVIEW_REQUIRED، صفر اصلاح و صفر امتناع معتبر تأییدشده. ۱۱۴۴ مورد هنوز بررسی محتوایی نشده‌اند؛ REVIEW_REQUIRED اولیهٔ ledger نشان انتظار ممیزی است، نه شکست محتوایی اثبات‌شده.
- سؤال کلی «خردمند چه ویژگی‌ای دارد؟» حمایت جزئی دارد؛ امتناع فعلی بدون رفع ابهام معتبر اعلام نشده است. پاسخ آن بازنویسی نشده است.
- روش بررسی AGENT_REVIEW در context مشترک است. مدل مستقل، verifier مستقل یا تأیید انسانی ادعا نمی‌شود.
- metadata citation از رجیستری کپی شده؛ تطبیق location با متن سند اصلی هنوز انجام نشده است.
- هیچ فایل تولید اصلی تغییر نکرده، هیچ تغییر در RAG_finance ایجاد نشده و API مدل فراخوانی نشده است.

## یافته‌های بازیابی

در tree شاخهٔ تعیین‌شده و شاخهٔ دیگر rag-named (`agent/rag20-pilot-validator`) checkpoint ممیزی محتوایی یا repairs مربوط به چت قطع‌شده پیدا نشد. این نتیجه اثبات نبودن فایل در تمام شاخه‌های احتمالی نیست. در تاریخچهٔ تولید، refinementهای پاسخ وجود دارد؛ آن‌ها در snapshot فعلی لحاظ شده‌اند و دوباره تولید نشده‌اند. آخرین سلول‌های واقعی notebookهای ثبت‌شده NB19-C215 و NB20-C82 هستند؛ C223 صرفاً در پیشینهٔ ارسالی گزارش شده و در snapshot notebook ثبت نشده است.

## ادامه بدون دوباره‌کاری

۱. `checkpoints/CURRENT.json` و hashهای آن را بخوانید. آخرین batch معنایی تکمیل‌شده `semantic_001_005` است؛ مورد بعدی position 6 است.
۲. بررسی ساختاری را بی‌دلیل تکرار نکنید؛ اگر snapshot عوض شده، فقط candidateهایی که ورودی یا پاسخشان تغییر کرده را invalidate کنید. ابزار ساختاری checkpoint قبلی را از همان snapshot ادامه می‌دهد و تصمیم‌های معنایی ledger را حفظ می‌کند.
۳. برای هر مورد، سؤال، همهٔ evidenceها، پاسخ و همهٔ claims را کامل بخوانید؛ از Gold، دانش بیرونی و excerpt انتخابی برای تولید یا اصلاح استفاده نکنید.
۴. هر batch جدید را با audit، support و span واقعی و سپس checkpoint ذخیره و reload کنید. هیچ مورد بررسی‌نشده را KEEP یا VALID_ABSTENTION معرفی نکنید.
۵. پس از ممیزی محتوایی تمام موارد، فقط REPAIRها را نسخه‌دار اصلاح کنید؛ original response/hash و revised response/hash محفوظ بمانند.
۶. سپس source/location، adapter واقعی NB19، freeze، ارزیابی جداگانه و handoff NB20 تکمیل شوند. آستانه‌های frozen تغییر نکنند.

اجرای آفلاین ابزارها:

```bash
python experiments/rag20/recovery_final_v1/audit_structure.py
python experiments/rag20/recovery_final_v1/verify_recovery.py
```

این ZIP فقط checkpoint ممیزی است و ورودی‌ها و پاسخ‌های اصلی را دوباره بسته‌بندی نمی‌کند. ابزار اول به source_cache و batchها و shardهای اصلی نیاز دارد؛ مسیر و commit دقیق منابع در SOURCE_SNAPSHOT ثبت شده و فایل‌های کش در workspace این اجرا موجودند. پیش از بازاجرای محلی ابزار، منابع مرجع را از همان snapshot و فقط‌خواندنی فراهم کنید. اجرای notebook، Run All یا import نهایی در این checkpoint مجاز و آماده اعلام نشده است.
