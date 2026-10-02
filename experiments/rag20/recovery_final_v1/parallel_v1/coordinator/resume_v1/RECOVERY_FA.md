مبنای تجمیع: commit 65b618ab92fb9e1ec7741faa9210f6a1de50f647 و checkpoint consolidated_796_20261002.
CURRENT این مسیر، overlay یازده رکورد جدید است؛ CURRENT مرکزیِ آن commit همچنان snapshot مبنای 796 است. برای بازیابی 807، هر checkpoint referenced را به ترتیب بخوان؛ hash فایل‌ها و previous_batches را بررسی کن؛ decisions.jsonl را با incremental_review.append_decisions روی state مبنا اعمال و validate و preserve کن. replay دقیق no-op است.
فایل‌های ممیزان قبلی تغییر نکرده‌اند. مالک ادامه در این مسیر هماهنگ‌کننده است. اصلاحات original/previous/revised hash و rechecked دارند. هیچ API مدل یا Gold استفاده نشده؛ AGENT_REVIEW مستقل نیست.
ممیزی باقی‌مانده به ترتیب position از 326 ادامه دارد؛ source/location، adapter و handoff NOT_RUN هستند.
