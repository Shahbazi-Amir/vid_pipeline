# Production Hardening Checklist

هدف این برنامه تبدیل `vid_pipeline` به یک سرویس قابل‌اعتماد برای دریافت File، URL یا GitHub Release و تولید خروجی رونویسی کنترل‌شده بود. هر مشکل جداگانه اصلاح شد و برای مسیرهای تغییرکرده regression/runtime test اضافه و اجرا شد.

## وضعیت نهایی

- کل مشکلات اصلی: **10**
- حل‌شده: **10**
- باقی‌مانده: **0**
- وضعیت Production Hardening: **DONE**

## نتیجه تست نهایی Hardening

روی کد Head با SHA زیر تست هدفمند یک‌جا اجرا شد:

`158755dc6a2f1a4c5ccffa9ae27fcd5b676f9a32`

نتیجه:

- **37 passed / 0 failed** در یک اجرای مشترک pytest.
- `compileall` روی workspace بازسازی‌شده‌ی source/test بدون خطا بود.
- Queue/timeout/cancel: **9 PASS**.
- Storage/S3/state concurrency: **4 PASS**.
- Source adapters و SSRF/GitHub Release: **5 PASS**.
- Targeted retry/performance policy: **3 PASS**.
- Model policy/API source contract: **2 PASS**.
- Online Worker E2E: **3 PASS**.
- Runtime Whisper model reuse: **2 PASS**.
- AI/Human review guards: **4 PASS**.
- ASR artifact cache/integrity: **4 PASS**.
- Canonical processing core: **1 PASS**.

> محدودیت محیط تست: GitHub Actions پروژه قبلاً عمداً حذف شده‌اند و Runner فعلی DNS مستقیم `github.com`/`raw.githubusercontent.com` برای `git clone` ندارد. بنابراین ادعای اجرای کل legacy test-suite روی یک checkout کامل نداریم. برای تست Hardening، source و testهای مرتبط از همان Head SHA توسط GitHub Connector خوانده و در workspace محلی بازسازی شدند و suite هدفمند 37 تستی به‌صورت یک‌جا اجرا شد. خطاهای بازسازی محلی قبل از شمارش نهایی اصلاح شدند و به‌عنوان regression پروژه شمرده نشدند.

## 1. جلوگیری از Final شدن متن بی‌کیفیت — DONE

### مشکل
Worker آنلاین پایان ASR را معادل موفقیت می‌گرفت و خروجی خراب می‌توانست `completed` و قابل Delivery شود.

### راه‌حل اجراشده
- Quality Gate واقعی بر اساس confidence، log probability، no-speech probability و review flags.
- Raw ASR evidence بر خلاصه‌ی Document اولویت دارد.
- خروجی ردشده `review_required` می‌شود، نه `completed`.
- `final/` و `delivery/` stale در retry پاک می‌شوند.
- Online Client وضعیت `review_required` را terminal می‌شناسد.
- thresholdها از Environment قابل تنظیم‌اند.

### تست
Good/low/raw-evidence/empty transcript و Online E2E پوشش داده شدند؛ low-quality output Final نمی‌شود و audio evidence برای review حفظ می‌شود.

## 2. Job timeout نامناسب برای ASR طولانی — DONE

### مشکل
RQ بدون `job_timeout` صریح می‌توانست از timeout کوتاه پیش‌فرض استفاده کند.

### راه‌حل اجراشده
- `QueuePolicy` مرکزی.
- timeout پیش‌فرض **43200 ثانیه / 12 ساعت**.
- timeout هم Queue default و هم metadata هر Job است.
- `result_ttl` و `failure_ttl` صریح و validated هستند.
- Cancel queued از `Job.cancel()` و Cancel started از stop command استفاده می‌کند.
- Auto-retry کور برای ASR سنگین اضافه نشد.

### تست
Queue policy + cancel: **9 PASS**.

## 3. ناسازگاری Profile و Model provisioning — DONE

### مشکل
Profileها مدل‌هایی مثل `small` و `large-v3` انتخاب می‌کردند در حالی که artifact کنترل‌شده‌ی پروژه `large-v3-turbo` بود.

### راه‌حل اجراشده
- یک منبع حقیقت واحد در `profiles.py`.
- مدل Production فعلی: `large-v3-turbo`.
- `fast`, `balanced`, `accurate` فعلاً همگی به artifact provisionable پروژه resolve می‌شوند؛ تفاوت Profile از policy پردازش اعمال می‌شود.
- named model غیرقابل provision قبل از Upload/Queue رد می‌شود.
- API، Client، Worker، `JobRequest`، `TranscriptionConfig` و CLIهای مرتبط هم‌راستا شدند.
- Local CT2 path فقط در مسیر local/development مجاز است.

### تست
Profile/model policy و API validation در suite نهایی PASS شدند.

## 4. Cache مدل در Docker/Worker — DONE

### مشکل
Docker متغیر cache متفاوتی از ASR manager داشت و warm execution می‌توانست دوباره download/extract یا full-hash انجام دهد.

### راه‌حل اجراشده
- متغیر واحد `VID_PIPELINE_ASR_CACHE=/models/asr`.
- volume پایدار `/models` در Worker.
- artifact قبل از نصب با size/SHA-256 بررسی می‌شود.
- cache خراب quarantine/reprovision می‌شود.
- بعد از یک full integrity validation، signature اندازه/mtime داخل process نگه داشته می‌شود؛ فایل دست‌نخورده در Job بعدی دوباره مدل ~GB را کامل hash نمی‌کند.

### تست
ASR cache/integrity: **4 PASS**؛ cache miss→hit، corruption recovery، SHA mismatch hard-fail و warm cache بدون re-hash.

## 5. Reload شدن مدل برای هر Job — DONE

### مشکل
ساخت `WhisperModel` برای هر Job latency و RAM churn زیادی ایجاد می‌کرد.

### راه‌حل اجراشده
- process-level runtime model cache بر اساس `(model path, device, compute_type)`.
- `VID_PIPELINE_PERSISTENT_MODEL=1` به‌صورت پیش‌فرض.
- Worker Docker از `rq.worker.SimpleWorker` استفاده می‌کند تا Jobهای متوالی در همان process اجرا شوند و مدل resident بماند.
- امکان opt-out برای debug/deployment خاص باقی مانده است.

### تست
Runtime model reuse: **2 PASS**؛ دو transcription متوالی یک load دارند و opt-out دوباره load می‌کند.

## 6. پردازش تکراری و هزینه اضافی ASR — DONE

### مشکل
multi-pass کامل فایل روی CPU می‌توانست زمان ASR را چند برابر کند.

### راه‌حل اجراشده
- Production همیشه یک Primary full-file ASR دارد.
- `fast`: بدون retry.
- `balanced`: فقط segmentهای مشکوک، حداکثر 40 segment.
- `accurate`: targeted retry گسترده‌تر، حداکثر 120 segment.
- `full_file_additional_passes=0` برای مسیر Production.
- Candidateهای retry خودکار حقیقت نهایی فرض نمی‌شوند و disagreement به review می‌رود.

### تست
Targeted retry policy: **3 PASS**؛ و canonical core نیز تأیید می‌کند فقط یک Primary ASR اجرا می‌شود.

## 7. دو Pipeline متفاوت برای Online و Standalone — DONE

### مشکل
Worker آنلاین مسیر ساده‌شده و متفاوتی از منطق اصلی پردازش داشت.

### راه‌حل اجراشده
- `server/processing.py` به Canonical Deployable Processing Core تبدیل شد.
- ترتیب مشترک: Normalize → Primary ASR → Targeted Retry → Clean → Quality Gate.
- Worker فقط orchestration صف، state، artifact و terminal status را مدیریت می‌کند.
- `core-manifest.json` و timing/diagnosticها تولید می‌شوند.

### تست
Canonical processing core: **1 PASS** و Online Worker E2E: **3 PASS**.

## 8. Review و Verification ناکافی — DONE

### مشکل
پر بودن decisionها می‌توانست بدون اثبات شنیدن صوت به `human_verified` برسد و AI/ChatGPT نیز عملاً قابل ثبت به‌عنوان reviewer انسانی بود.

### راه‌حل اجراشده
- `ai_reviewed` از `human_verified` جدا شد.
- AI review هرگز `human_audio_verification=true` یا promotion انسانی تولید نمی‌کند.
- reviewerهای AI/LLM مانند ChatGPT/OpenAI/GPT/Claude/Gemini/Copilot برای `human_verified` رد می‌شوند.
- Human verification نیازمند وجود audio، `review_type=human_audio`، `audio_review_confirmed=true` و `audio_reviewed=true` برای تمام required itemهاست.
- verification report شامل hash صوت و corrections است.
- export/copy نهایی نیز فقط evidence-backed human verification را نهایی انسانی می‌داند.

### تست
AI/Human review security guards: **4 PASS**.

## 9. ورودی یکپارچه File / URL / GitHub Release — DONE

### مشکل
API عمدتاً Upload فایل را پوشش می‌داد و URL/Release به مسیرهای قدیمی یا GitHub Actions وابسته بودند.

### راه‌حل اجراشده
- `SourceMaterializer` مشترک برای `upload`, `url`, `github_release`.
- هر سه Source از `POST /v1/jobs` وارد همان Queue/Core می‌شوند.
- URL فقط HTTP/HTTPS عمومی؛ loopback/private/link-local/internal و DNS rebinding به IP خصوصی رد می‌شوند.
- GitHub Release asset از GitHub API با نام asset دقیق، size limit و token اختیاری دریافت می‌شود.
- Online Client متدهای URL و GitHub Release دارد.
- GitHub Actions در runtime این معماری هیچ نقشی ندارد.

### تست
Source/SSRF/GitHub Release: **5 PASS** و API queue contract نیز PASS شد.

## 10. Production storage/state/concurrency hardening — DONE

### مشکل
S3 adapter end-to-end materialization نداشت و snapshot قدیمی Worker می‌توانست Cancel/Retry جدید API را overwrite کند.

### راه‌حل اجراشده
- ObjectStore interface شامل `put_file`, `open`, `materialize`, `size`, `list`.
- S3 worker input واقعاً به workspace محلی materialize می‌شود و hash/size Upload کنترل می‌شود.
- artifactهای اعلام‌شده پس از ساخته‌شدن به ObjectStore publish می‌شوند.
- API برای local file از `FileResponse` و برای ObjectStore از streaming استفاده می‌کند.
- Job payload دارای `_revision` است و `put_job` به compare-and-swap تبدیل شد.
- `transition_job` برای Cancel/Retry atomic و status-aware است.
- Worker بعد از ASR revision جدید را بررسی می‌کند و snapshot قدیمی نمی‌تواند state جدید را overwrite یا artifact را publish کند.
- Cancel queued/running در RQ به‌درستی تفکیک شد.
- Docker API mountpoint `/data/storage` را برای UID غیر root آماده می‌کند تا named volume در اولین Deploy با permission error نخوابد.

### تست
Storage/S3/state concurrency: **4 PASS**، Queue cancel: PASS، Online Cancel→Retry E2E: PASS.

## جمع‌بندی

Hardening تعریف‌شده در این Checklist **10/10 تکمیل شده است**. معیار نهایی این مرحله، سبز بودن suite هدفمند مسیرهای تغییرکرده بود که با **37/37 PASS** برآورده شد. Merge این Branch به `main` خارج از این Checklist است و باید جداگانه و با تأیید صریح انجام شود.
