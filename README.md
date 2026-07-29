# Video Transcript Pipeline

The project supports three distinct execution modes:

1. Online submission from a lightweight computer
2. Direct processing on a machine with worker dependencies
3. Docker deployment of the API and worker

## Lightweight macOS client (recommended)

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
