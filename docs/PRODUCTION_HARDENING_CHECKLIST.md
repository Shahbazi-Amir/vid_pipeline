# Production Hardening Checklist

هدف این برنامه تبدیل `vid_pipeline` به یک سرویس قابل‌اعتماد برای دریافت فایل، URL یا GitHub Release و تولید خروجی رونویسی کنترل‌شده است. هر مورد جداگانه اصلاح و بعد تست می‌شود.

## وضعیت کلی

- کل مشکلات اصلی: **10**
- حل‌شده: **3**
- باقی‌مانده: **7**

## 1. جلوگیری از Final شدن متن بی‌کیفیت — DONE

### مشکل
Worker آنلاین صرفاً پایان یافتن ASR را معادل موفقیت می‌گرفت و `quality-report.json` را با `valid: true` ثابت می‌ساخت. بنابراین خروجی خراب می‌توانست `completed` و قابل دانلود به‌عنوان Delivery شود.

### راه‌حل اجراشده
- Quality Gate واقعی با استفاده از confidence، log probability، no-speech probability و review flags اضافه شد.
- Raw ASR evidence حفظ می‌شود و بر confidence خلاصه‌شده Document اولویت دارد.
- خروجی ردشده به `review_required` می‌رود، نه `completed`.
- برای خروجی ردشده هیچ `delivery/` یا `final/` باقی نمی‌ماند.
- در retry، Final/Delivery قدیمی پاک می‌شود تا خروجی stale قابل انتشار نباشد.
- Online client وضعیت `review_required` را terminal می‌شناسد و در `wait()` گیر نمی‌کند.
- thresholdها با Environment قابل تنظیم هستند:
  - `VID_PIPELINE_MIN_QUALITY_SCORE` (default: 70)
  - `VID_PIPELINE_MAX_LOW_SEGMENT_RATIO` (default: 0.35)
  - `VID_PIPELINE_MAX_FLAGGED_SEGMENT_RATIO` (default: 0.60)

### تست
- good transcript: `pass`, overall score = 86.0
- low-confidence transcript: `review_required`, overall score = 34.9
- low-quality raw ASR + optimistic document confidence: `review_required`, overall score = 19.8
- empty transcript: `review_required`
- یک regression در default policy loading هنگام تست کشف و قبل از نهایی شدن اصلاح شد.

> توجه: GitHub Actions workflows قبلاً از repository حذف شده‌اند؛ بنابراین در این مرحله CI خودکار PR وجود ندارد و تست بالا به‌صورت targeted runtime test اجرا شده است.

## 2. Job timeout نامناسب برای ASR طولانی — DONE

### مشکل
`RedisJobQueue.enqueue()` هیچ `job_timeout` صریحی تعیین نمی‌کرد. RQ به‌صورت پیش‌فرض Job را بعد از 180 ثانیه timeout می‌کند؛ این مقدار برای ASR فایل‌های صوتی/ویدیویی طولانی مناسب نیست.

### راه‌حل اجراشده
- `QueuePolicy` مرکزی برای تنظیمات عملیاتی RQ اضافه شد.
- timeout پیش‌فرض ASR برابر **43200 ثانیه / 12 ساعت** شد.
- timeout هم به‌عنوان `default_timeout` خود Queue و هم به‌صورت `job_timeout` روی هر Job نوشته می‌شود.
- تنظیمات از Environment قابل تغییر و دارای validation هستند:
  - `VID_PIPELINE_JOB_TIMEOUT_SECONDS=43200`، بازه مجاز 5 دقیقه تا 7 روز.
  - `VID_PIPELINE_RESULT_TTL_SECONDS=604800`، پیش‌فرض 7 روز.
  - `VID_PIPELINE_FAILURE_TTL_SECONDS=2592000`، پیش‌فرض 30 روز.
- failure/result metadata به‌اندازه کافی نگه داشته می‌شوند تا عیب‌یابی Jobهای چندساعته ممکن باشد.
- `compose.yml` و `.env.example` به‌روزرسانی شدند.
- Auto-retry کور عمداً اضافه نشد؛ retry کنترل‌شده در API باقی ماند.

### تست
- default policy: `43200 / 604800 / 2592000` — PASS
- explicit deployment overrides — PASS
- invalid/unsafe env values — PASS
- Redis queue constructor receives `default_timeout` — PASS
- every enqueue receives explicit `job_timeout`, `result_ttl`, `failure_ttl` — PASS
- مجموع تست‌های targeted: **7 passed**
- اولین اجرا ناسازگاری سقف retention را پیدا کرد؛ بعد از اصلاح دوباره همه تست‌ها PASS شدند.

## 3. ناسازگاری Profile و Model provisioning — DONE

### مشکل
`fast` به `small` و `accurate` به `large-v3` نگاشت می‌شدند، در حالی که Provisioner پروژه فقط artifact کنترل‌شده و integrity-pinned مدل `large-v3-turbo` را دارد. علاوه بر آن `OnlineClient` و `TranscriptionConfig` و `JobRequest` defaultهای `small` داشتند و API مدل را قبل از Queue validate نمی‌کرد.

### راه‌حل اجراشده
- `src/vid_pipeline/profiles.py` به منبع حقیقت واحد سیاست مدل تبدیل شد.
- مدل production فعلی به‌صورت صریح `PROJECT_ASR_MODEL=large-v3-turbo` تعریف شد.
- تا زمانی که artifact کنترل‌شده جدید اضافه نشده، هر سه profile یعنی `fast`, `balanced`, `accurate` به همین مدل provisionable نگاشت می‌شوند؛ تفاوت سرعت/دقت profileها بعداً از inference policy و targeted passes اعمال می‌شود، نه با مدل غیرقابل provision.
- explicit named modelهای بدون artifact مانند `small`, `medium`, `large-v3` رد می‌شوند.
- local CT2 directory فقط برای مسیر local/development مجاز است؛ API remote اجازه local path نمی‌دهد.
- Online Client قبل از hash/upload فایل، profile/model را validate می‌کند تا فایل حجیم بیهوده Upload نشود.
- API دوباره به‌صورت مستقل model policy را validate می‌کند و request نامعتبر را با HTTP 422 قبل از enqueue رد می‌کند.
- Worker نیز دفاع مستقل دارد و پیش از ASR دوباره model را resolve می‌کند.
- `TranscriptionConfig`, `JobRequest` و `.env.example` از default واحد `large-v3-turbo` استفاده می‌کنند.
- `vid-accuracy --model` نیز به همین policy وصل شد تا CLI فرعی نتواند model نام‌دار غیرقابل provision وارد کند.
- regression test جدید در `tests/test_model_policy.py` اضافه شد؛ شامل API contract برای هر سه profile و عدم enqueue مدل/profile نامعتبر.

### تست
- `fast -> large-v3-turbo` — PASS
- `balanced -> large-v3-turbo` — PASS
- `accurate -> large-v3-turbo` — PASS
- reject `small` — PASS
- reject `medium` — PASS
- reject `large-v3` — PASS
- reject unknown profile — PASS
- local model path allowed in local mode — PASS
- local model path blocked in remote/production mode — PASS
- targeted runtime policy checks: **9/9 passed**
- تست‌های API contract در repository اضافه شده‌اند؛ CI خودکار اجرا نشد چون طبق تصمیم قبلی پروژه تمام GitHub Actions workflows حذف شده‌اند و Runner فعلی نیز DNS مستقیم GitHub برای clone ندارد.

## 4. Cache مدل در Docker/Worker — TODO

### مشکل
مسیر cache تعریف‌شده در Docker با متغیری که ASR manager می‌خواند همسان نیست و احتمال download/extract مجدد مدل وجود دارد.

### راه‌حل برنامه‌ریزی‌شده
- یکسان‌سازی `VID_PIPELINE_ASR_CACHE` و volume `/models`.
- health/startup validation برای model cache.
- تست cache hit در اجرای دوم.

## 5. Reload شدن مدل برای هر Job — TODO

### مشکل
Worker برای هر پردازش WhisperModel جدید می‌سازد.

### راه‌حل برنامه‌ریزی‌شده
- process-level model cache / reusable processor.
- کنترل thread/process safety.
- تست اینکه چند Job پشت‌سرهم فقط یک بار مدل را load کنند.

## 6. پردازش‌های تکراری و هزینه اضافی ASR/Audio scan — TODO

### مشکل
در بعضی مسیرها کل فایل چند بار ASR/scan می‌شود؛ multi-pass روی CPU بسیار کند است.

### راه‌حل برنامه‌ریزی‌شده
- primary pass + targeted retry فقط برای segmentهای مشکوک.
- reuse checkpointها و metadata probe.
- benchmark قبل/بعد.
- در صورت نیاز استفاده از duration canonical برای سیاست‌های resource/timeout بدون probe تکراری.

## 7. دو Pipeline متفاوت برای Online و Standalone — TODO

### مشکل
Online Worker مسیر ساده‌شده‌ای دارد که بسیاری از قابلیت‌های canonical standalone pipeline را اجرا نمی‌کند.

### راه‌حل برنامه‌ریزی‌شده
- استخراج یک canonical processing service مشترک.
- CLI، API و Worker همگی همان service را استفاده کنند.
- contract/integration tests مشترک.

## 8. Review و Verification ناکافی — TODO

### مشکل
Review ساختاری می‌تواند متن غلط ولی هم‌شکل را بپذیرد و وضعیت‌هایی مانند human/audio verified بیش از واقعیت ادعا شده‌اند.

### راه‌حل برنامه‌ریزی‌شده
- جداسازی `machine_draft`, `review_required`, `ai_reviewed`, `human_verified`.
- ممنوعیت `human_verified` بدون evidence انسانی واقعی.
- semantic/content-preservation و audio-linked review gates.
- regression tests روی نمونه‌های خرابی واقعی Repo.

## 9. ورودی یکپارچه File / URL / GitHub Release — TODO

### مشکل
API آنلاین عمدتاً upload فایل را پوشش می‌دهد؛ URL و Release هنوز به مسیرهای متفاوت/قدیمی وابسته‌اند.

### راه‌حل برنامه‌ریزی‌شده
- Source Adapter مشترک برای File، URL و GitHub Release asset.
- همه ورودی‌ها بعد از ingest وارد یک Job pipeline شوند.
- تست end-to-end هر سه نوع ورودی.

## 10. Production storage/state hardening — TODO

### مشکل
S3 adapter با Worker فعلی end-to-end سازگار نیست و state updateها در برابر concurrent retry/cancel حفاظت کافی ندارند.

### راه‌حل برنامه‌ریزی‌شده
- materialization interface مستقل از Local path.
- S3-compatible worker flow.
- atomic/versioned state transitions.
- concurrency/retry/cancel tests.
