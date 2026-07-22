# Video Transcript Pipeline

یک پایپ‌لاین مستقل برای تبدیل لینک ویدئو به متن خام و متن نهایی پاک‌سازی‌شده.

این مخزن به هیچ مخزن دیگری وابسته نیست و همهٔ ورودی‌ها، وضعیت پردازش و خروجی‌ها را داخل پوشهٔ `outputs/` مدیریت می‌کند.

## مسیر پردازش

```text
Video URL
→ بررسی منبع با yt-dlp
→ دانلود ویدئو
→ استخراج و استانداردسازی صوت با ffmpeg
→ رونویسی با faster-whisper
→ پاک‌سازی متن با حفظ ترتیب گفت‌وگو
→ خروجی Markdown و TXT
```

## ویژگی‌ها

- دریافت مستقیم لینک ویدئو؛
- پشتیبانی از سایت‌هایی که `yt-dlp` پشتیبانی می‌کند؛
- پردازش resume-safe با `state.json`؛
- خروجی خام زمان‌دار برای عیب‌یابی؛
- خروجی نهایی بدون timecode؛
- حفظ ترتیب اصلی segmentها؛
- یکسان‌سازی حروف فارسی و عربی؛
- حذف تکرارهای مجاور و آشکار؛
- تولید Markdown و متن ساده؛
- بدون commit خودکار خروجی‌ها و بدون اتصال به مخزن خارجی.

## نیازمندی‌ها

- Python 3.10 یا جدیدتر
- `ffmpeg` و `ffprobe`
- فضای کافی برای دانلود و فایل صوتی

### نصب

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
```

در macOS:

```bash
brew install ffmpeg
```

در Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## اجرای ساده

```bash
vid-pipeline run-url 'https://example.com/video'
```

برای اجرای فارسی روی CPU:

```bash
vid-pipeline run-url 'https://example.com/video' \
  --language fa \
  --model small \
  --device cpu \
  --compute-type int8
```

برای تعیین نام job و پوشهٔ خروجی:

```bash
vid-pipeline run-url 'https://example.com/video' \
  --name interview-01 \
  --output-root outputs
```

## ساختار خروجی

```text
outputs/<job-id>/
├── state.json
├── source.json
├── video-info.json
├── result.json
├── video/
│   └── video.*
├── audio/
│   └── audio-16k-mono.wav
├── raw/
│   ├── transcript.raw.json
│   └── transcript.raw.md
└── final/
    ├── transcript.final.md
    └── transcript.final.txt
```

فایل اصلی قابل استفاده:

```text
outputs/<job-id>/final/transcript.final.md
```

## مشاهدهٔ وضعیت

پس از اجرای اولیه، شناسهٔ job در خروجی چاپ می‌شود:

```bash
vid-pipeline status <job-id> --output-root outputs
```

اجرای مجدد همان URL مراحل کامل‌شده را رد می‌کند. برای اجرای دوبارهٔ همهٔ مراحل:

```bash
vid-pipeline run-url 'https://example.com/video' --force
```

## پاک‌سازی یک خروجی Whisper موجود

```bash
vid-pipeline clean transcript.raw.json \
  --markdown transcript.final.md \
  --text transcript.final.txt \
  --title 'عنوان ویدئو'
```

## بررسی لینک بدون دانلود

```bash
vid-pipeline inspect 'https://example.com/video'
```

## صداقت خروجی

خروجی نهایی به‌صورت ماشینی پاک‌سازی می‌شود؛ یعنی ترتیب گفت‌وگو حفظ، timecode حذف و خطاهای شکلی و تکرارهای آشکار اصلاح می‌شوند. تشخیص قطعی نام‌ها، اعداد یا واژه‌های بسیار نامفهوم بدون گوش‌دادن انسانی تضمین نمی‌شود.

## تست و کیفیت کد

```bash
ruff check src tests
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

CI همین بررسی‌ها را روی push و pull request اجرا می‌کند.

## مرحلهٔ بعد

رابط کاربری وب روی همین هسته ساخته خواهد شد و از همان فرمان `run-url` و ساختار خروجی استفاده می‌کند.
