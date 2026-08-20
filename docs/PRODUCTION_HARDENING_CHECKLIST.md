# Production Hardening Checklist

هدف این برنامه تبدیل `vid_pipeline` به یک سرویس قابل‌اعتماد برای دریافت فایل، URL یا GitHub Release و تولید خروجی رونویسی کنترل‌شده است. هر مورد جداگانه اصلاح و بعد تست می‌شود.

## وضعیت کلی

- کل مشکلات اصلی: **10**
- حل‌شده: **1**
- باقی‌مانده: **9**

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

## 2. Job timeout نامناسب برای ASR طولانی — TODO

### مشکل
RQ enqueue برای پردازش‌های چنددقیقه‌ای/چندساعته timeout صریح و متناسب با ASR ندارد.

### راه‌حل برنامه‌ریزی‌شده
- timeout صریح و قابل تنظیم برای Jobهای ASR.
- تعیین timeout بر اساس duration/سقف امن.
- تست با Job مصنوعی طولانی و بررسی enqueue metadata.

## 3. ناسازگاری Profile و Model provisioning — TODO

### مشکل
Profileها `small`/`large-v3-turbo`/`large-v3` تولید می‌کنند ولی model provisioner پروژه فقط artifact کنترل‌شده محدودی را قبول می‌کند.

### راه‌حل برنامه‌ریزی‌شده
- یک منبع حقیقت واحد برای model policy.
- validation قبل از enqueue.
- حذف defaultهای متناقض Client/API/Worker.
- تست تمام profileها.

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
