مبنای تجمیع: commit 65b618ab92fb9e1ec7741faa9210f6a1de50f647 و checkpoint consolidated_796_20261002.
CURRENT این مسیر overlay مجموع 36 رکورد جدید positions315–350 است؛ CURRENT مرکزی remote همچنان snapshot مبنای796 است. برای بازیابی832، checkpointهای referenced را به ترتیب بخوان؛ hash فایل‌ها و previous_batches را بررسی کن؛ decisions.jsonl را با incremental_review.append_decisions روی state مبنا اعمال و validate و preserve کن. replay دقیق no-op است.
فایل‌های ممیزان قبلی تغییر نکرده‌اند. مالک ادامه هماهنگ‌کننده است. اصلاحات original/previous/revised hash و rechecked دارند. Gold و API مدل استفاده نشده؛ AGENT_REVIEW مستقل نیست.
ادامه از351؛ source/location، adapter و handoff NOT_RUN هستند. پوشه interrupted_batches وارد هیچ شمارش یا checkpoint معتبر نیست.
