# Video Transcript Pipeline

The project supports four distinct execution modes:

1. GitHub Actions — URL
2. GitHub Actions — local file upload
3. Online API/server submission
4. Direct local/server processing (including Docker deployment)

## GitHub Actions — local files from a lightweight Mac

The local video is never committed. The client streams one confirmed file to a
private asset on a fixed draft GitHub Release, dispatches the worker workflow,
downloads and validates the transcript, and only then deletes the temporary
GitHub copy. The original local video is never deleted.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[client]'

export VID_PIPELINE_GITHUB_TOKEN="..."
export VID_PIPELINE_GITHUB_REPO="Shahbazi-Amir/vid_pipeline"

vid-pipeline github-submit-folder ./input_videos \
  --recursive \
  --confirm-each \
  --wait \
  --download \
  --output-root ./outputs \
  --delete-remote-after-success
```

FFmpeg, Whisper, Ollama, Docker and model downloads do not run on the Mac.
Each file requires separate confirmation, and only one file is uploaded at a
time. Input videos remain ignored by Git. Pressing Enter does not approve an
upload. Files at or above 2 GiB are rejected before upload.

Create a fine-grained GitHub personal access token scoped only to the target
repository with these minimum repository permissions:

- Contents: Read and write
- Actions: Read and write
- Metadata: Read

Store it only in `VID_PIPELINE_GITHUB_TOKEN`; the token is never written to
`.vid_pipeline/github/`, printed, or passed to a shell command. Request state is
written atomically to `.vid_pipeline/github/<request-id>.json`. Results are
downloaded to `outputs/<job-id>/final/`, including
`transcript.final.txt`.

## خروجی نهایی کم‌حجم

هر اجرای موفق در پوشه `delivery/` فقط سه فایل قابل تحویل می‌سازد:

```text
transcript.md
transcript.txt
transcript.timestamped.md
```

دو فایل اول از بهترین متن نهایی Pipeline (از جمله editorial یا بازبینی انسانی)
ساخته می‌شوند. فایل زمان‌بندی‌شده از segmentهای دارای زمان واقعی با اولویت
بازبینی انسانی، consensus مرحله Accuracy، machine segmentها و در نهایت raw ASR
ساخته می‌شود. اگر editorial نگاشت زمانی مطمئن نداشته باشد، متن آن برای فایل
زمان‌بندی‌شده استفاده نمی‌شود و timestamp جدیدی نیز ساخته نمی‌شود.

فایل‌های داخلی برای resume و review روی filesystem باقی می‌مانند، اما artifact
عادی GitHub Actions فقط همین سه فایل را دارد. گزینه `--keep-debug-artifacts`
برای درخواست نگه‌داری/انتشار artifact جداگانهٔ debug است؛ در failure نیز گزارش
تشخیصی جدا از خروجی عادی ساخته می‌شود.

Available GitHub commands:

```text
github-submit-file
github-submit-folder
github-run-url
github-job-status
github-resume
github-cleanup
```

Release Asset upload has no reliable byte-level resume. An interrupted upload
restarts that file from byte zero; a completed asset recorded in local state is
reused. Failed workflows keep the remote input for retry by default. Failed
post-validation deletion is recorded as `remote_cleanup_pending`, and
`github-resume` retries cleanup without uploading or processing again.

## GitHub Actions — URL

The existing URL workflow can be dispatched from the lightweight client:

```bash
vid-pipeline github-run-url "https://example.com/video.mp4" \
  --wait \
  --download \
  --output-root ./outputs
```

## Online API/server submission from a lightweight Mac

The Mac only hashes and uploads input files, watches job progress, and downloads
results. FFmpeg, Docker, Whisper, Ollama and model downloads are not required on
the client computer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[client]'

vid-pipeline submit-folder ./input_videos \
  --recursive \
  --server-url https://pipeline.example.com \
  --output-root ./outputs \
  --profile balanced \
  --model small \
  --language fa \
  --no-editorial \
  --wait \
  --download
```

Authentication can be provided without putting the token in shell history:

```bash
export VID_PIPELINE_SERVER_URL=https://pipeline.example.com
export VID_PIPELINE_API_TOKEN=replace-me
vid-pipeline submit-file ./input_videos/session-01.mp4 --wait --download
```

Client commands:

```text
submit-file
submit-folder
jobs
job-status
wait
download-results
```

Resumable state is stored under `.vid_pipeline/`. Completed files are not
uploaded again, and results are downloaded to `outputs/<job-id>/final/`.

## Direct local/server processing

These commands run FFmpeg and ASR on the current machine and therefore require
worker dependencies:

```bash
pip install -e '.[all]'
vid-pipeline run-url "https://example.com/video"
vid-pipeline run-file "/path/to/video.mp4" --no-editorial
vid-pipeline run-folder "/path/to/media" --recursive --no-editorial
```

## Docker deployment

The API image contains the control plane only. The worker image contains
FFmpeg/FFprobe and ASR dependencies. Whisper models are downloaded at runtime
into the model-cache volume, never during image build.

```bash
cp .env.example .env
docker compose up --build
```

Deployment architecture:

```text
Lightweight Client
    ↓
Online API / Control Plane
    ↓
Redis Background Worker
    ↓
Local or S3-compatible Artifact Storage
```

See [online architecture and deployment](docs/online-execution.md).

The core is callable from Python and is independent of GitHub Actions and
macOS. Overlapping chunk plans, conservative timestamp-aware merging, portable
artifact storage, provider-neutral review contracts, and final JSON, Markdown,
TXT, SRT, and VTT renderers live under `src/vid_pipeline/`.

See [deployment and worker usage](docs/deployment.md) for Linux, Docker, cache
mounts, online workers, profiles, and the deliberately unimplemented future
OpenAI review provider.

یک پایپ‌لاین مستقل برای تبدیل **یک لینک ویدئو** به متن فارسی خام، متن پاک‌سازی‌شده، متن ویرایش‌شده و بستهٔ بازبینی انسانی؛ بدون نیاز به API پولی.

## مسیر کامل پردازش

```text
Video URL
→ بررسی و دانلود ویدئو با yt-dlp
→ استخراج و استانداردسازی صوت با ffmpeg
→ رونویسی زمان‌دار فارسی با faster-whisper
→ پاک‌سازی تکرارها و خطاهای شکلی
→ بازسازی محدود با مدل متن‌باز محلی در Ollama
→ کنترل حفظ کامل محتوا و fallback به متن machine
→ تشخیص نام‌ها، اعداد و بخش‌های کم‌اعتماد
→ تولید کلیپ صوتی، گزارش کیفیت، SRT/VTT و رابط بازبینی
→ تأیید نهایی انسان و ارتقا به human_verified
```

نسخه‌های خام و ماشینی نگه‌داری می‌شوند تا خروجی نهایی قابل کنترل باشد. متن صفحهٔ منبع وارد رونویسی نمی‌شود؛ محتوا فقط از صوت ویدئو استخراج می‌شود.

## نیازمندی‌های اجرای مستقیم

- Python 3.10 یا جدیدتر
- `ffmpeg` و `ffprobe`
- Ollama برای ویرایش محلی
- فضای کافی برای مدل Whisper و مدل زبانی محلی

هیچ `OPENAI_API_KEY` یا Secret پولی لازم نیست.

## وضعیت کیفیت و بازبینی

جریان‌های عادی `run-url`، `run-file` و `run-folder` پردازش ماشینی را از
تأیید انسانی جدا می‌کنند. `machine_processing_complete` فقط یعنی ASR و متن
ماشینیِ content-preserving موجود است. پس از تحلیل کیفیت بدون متن مرجع و
pre-review، نتیجه در صورت وجود بخش مشکوک `human_review_required` و در غیر این
صورت `completed` است. فقط اعمال بازبینی انسانی مقدار
`review_status: human_verified` می‌سازد.

`--no-editorial` فقط ویرایش سبکی را خاموش می‌کند؛ Accuracy، selective retry،
pre-review و review package همچنان اجرا می‌شوند. profile سریع از `small`،
profile متعادل از `large-v3-turbo` با retry انتخابی، و profile دقیق از
`large-v3` با verification بیشتر استفاده می‌کند. `--model` صریح این انتخاب را
override می‌کند. Context و glossary فقط bias محافظه‌کارانه‌اند و صوت منبع حقیقت
باقی می‌ماند.

`run-folder` پس از خطای هر فایل، فایل‌های بعدی را ادامه می‌دهد، اما آن خطا را در
summary ثبت می‌کند و در صورت وجود هر failure با exit code غیرصفر پایان می‌یابد.

Quality بدون reference شامل confidence و anomaly است و WER/CER ادعا نمی‌کند.

## سنجش واقعی دقت

برای برآورد دقت، یک فایل JSONL از ویدئوهای دارای متن مرجع بسازید:

```json
{"id":"clip-01","reference":"متن مرجع انسانی","hypothesis":"خروجی پایپ‌لاین"}
```

سپس WER و CER کل مجموعه را محاسبه کنید:

```bash
vid-accuracy evaluate-corpus benchmark.jsonl --output benchmark-report.json
```

شکست مرحلهٔ Accuracy به‌صورت پیش‌فرض اجرای پایپ‌لاین را ناموفق می‌کند و در
`result.json` ثبت می‌شود. فقط برای نگه‌داشتن خروجی امن قبلی در حالت اختیاری،
`VID_PIPELINE_ACCURACY_REQUIRED=false` را تنظیم کنید.

## نصب محلی

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'

ollama pull qwen2.5:7b
ollama serve
```

## اجرای کامل با یک لینک

```bash
vid-pipeline run-url 'https://example.com/video.mp4' \
  --language fa \
  --model large-v3-turbo \
  --editorial-model qwen2.5:7b
```

پس از پایان این فرمان، مرحله Review به‌صورت خودکار اجرا می‌شود و تا وقتی موارد مشکوک توسط انسان تعیین تکلیف نشوند، `result.json` وضعیت `human_review_required` خواهد داشت.

برای نمایش آدرس صفحهٔ اصلی در فایل نهایی، در حالی که دانلود از لینک مستقیم رسانه انجام می‌شود:

```bash
vid-pipeline run-url 'https://cdn.example.com/video.mp4' \
  --source-url 'https://example.com/video-page' \
  --title 'عنوان ویدئو' \
  --network 'نام ناشر' \
  --date '۱۴۰۴/۰۲/۳۰' \
  --editorial-context 'موضوع و نام‌های مهم'
```

## خروجی

```text
outputs/<job-id>/
├── state.json
├── source.json
├── video-info.json
├── result.json
├── video/
├── audio/
│   └── audio-16k-mono.wav
├── raw/
│   ├── transcript.raw.json
│   └── transcript.raw.md
├── machine/
│   ├── transcript.machine.md
│   └── transcript.machine.txt
├── review/
│   ├── manifest.json
│   ├── uncertain-spans.json
│   ├── editorial-audit.json
│   ├── quality-report.json
│   ├── assistant-review-package.json
│   ├── transcript.review.srt
│   ├── transcript.review.vtt
│   ├── review.html
│   ├── corrections.template.json
│   └── clips/
├── human/
│   ├── transcript.human.txt
│   ├── transcript.human.md
│   ├── transcript.human.srt
│   ├── transcript.human.vtt
│   └── verification.json
└── final/
    ├── transcript.final.md
    ├── transcript.final.txt
    ├── transcript.final.srt
    ├── transcript.final.vtt
    ├── editorial-report.json
    ├── review-package.zip
    └── human-verification.json
```

فایل‌های `human/` و خروجی‌های زمان‌دار `final/` بعد از اعمال بازبینی انسانی ساخته می‌شوند.

## بازبینی انسانی

صفحه زیر را در مرورگر باز کنید و برای هر مورد تصمیم ثبت کنید:

```text
outputs/<job-id>/review/review.html
```

سپس فایل `corrections.json` را اعمال کنید:

```bash
vid-review apply outputs/<job-id> corrections.json \
  --reviewer 'نام بازبین' \
  --promote
```

فقط بعد از تعیین تکلیف تمام موارد اجباری، وضعیت زیر ثبت می‌شود:

```json
{
  "status": "completed",
  "review_status": "human_verified",
  "human_audio_verification": true
}
```

راهنمای کامل: [`docs/human-review.md`](docs/human-review.md)

## ویرایش یک رونویسی موجود

```bash
vid-pipeline edit transcript.raw.json \
  --markdown transcript.final.md \
  --text transcript.final.txt \
  --title 'عنوان ویدئو' \
  --source-url 'https://example.com/video'
```

## اجرای بدون مدل زبانی

```bash
vid-pipeline run-url 'https://example.com/video' --no-editorial
```

در این حالت متن machine به‌عنوان پایهٔ final استفاده می‌شود، اما مرحله Review همچنان بستهٔ کنترل انسانی را تولید می‌کند.

## GitHub Actions

Workflow با نام **Process video URL**:

1. ویدئو و صوت را پردازش می‌کند.
2. مدل Whisper را روی CPU و `int8` یک‌بار روی کل صوت اجرا می‌کند.
3. در حالت پیش‌فرض `fast` فقط بخش‌های کم‌اطمینان را دوباره پردازش می‌کند.
4. Ollama و مدل محلی را داخل همان runner نصب و اجرا می‌کند.
5. بستهٔ Review را در `final/review-package.zip` قرار می‌دهد.
6. فقط متن‌ها و گزارش‌های لازم را به‌صورت Artifact با ماندگاری ۳۰ روز منتشر
   می‌کند؛ ویدئو، WAV و کلیپ‌های موقت داخل Artifact قرار نمی‌گیرند. فایل‌های
   تولیدی روی شاخهٔ `main` کامیت نمی‌شوند.

هیچ Secret لازم نیست. علاوه بر اجرای دستی، افزودن فایل `runs/*.request.json` نیز workflow را اجرا می‌کند.

نمونهٔ درخواست:

```json
{
  "media_url": "https://cdn.example.com/video.mp4",
  "source_url": "https://example.com/video-page",
  "name": "sample-video",
  "title": "عنوان ویدئو",
  "network": "نام ناشر",
  "date": "۱۴۰۴/۰۲/۳۰",
  "whisper_model": "large-v3-turbo",
  "editorial_model": "qwen2.5:7b",
  "accuracy_mode": "fast"
}
```

حالت‌های `balanced` و `maximum` برای مقایسهٔ چند اجرای کامل ASR باقی مانده‌اند،
اما روی ویدئوهای طولانی زمان بسیار بیشتری می‌گیرند.

## اصول ویرایش و بازبینی

- معنا و ترتیب گفت‌وگو حفظ می‌شود.
- نام، عدد، نقل‌قول یا ادعای تازه بدون تأیید انسان افزوده نمی‌شود.
- خروجی ناقص مدل زبانی خودکار رد و با متن machine جایگزین می‌شود.
- پیشنهاد واژه‌نامه مستقیماً اعمال نمی‌شود و نیازمند تصمیم بازبین است.
- عبارت غیرقابل‌بازیابی با `[نامفهوم]` مشخص می‌شود.
- همه تغییرات، هش فایل‌ها و نام بازبین در گزارش verification ثبت می‌شود.

## تست

```bash
ruff check src tests
pytest -q
python -m compileall -q src tests
```
