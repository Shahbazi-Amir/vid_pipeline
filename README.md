# Video Transcript Pipeline

یک پایپ‌لاین مستقل برای تبدیل **یک لینک ویدئو** به متن فارسی خام، متن پاک‌سازی‌شده و متن نهایی ویرایش‌شده؛ بدون نیاز به API پولی.

## مسیر کامل پردازش

```text
Video URL
→ بررسی و دانلود ویدئو با yt-dlp
→ استخراج و استانداردسازی صوت با ffmpeg
→ رونویسی زمان‌دار فارسی با faster-whisper
→ پاک‌سازی تکرارها و خطاهای شکلی
→ بازسازی معنایی با مدل متن‌باز محلی در Ollama
→ گوینده‌بندی و موضوع‌بندی
→ خروجی نهایی Markdown و TXT
```

نسخه‌های خام و ماشینی نیز نگه‌داری می‌شوند تا خروجی نهایی قابل کنترل باشد. متن صفحهٔ منبع وارد رونویسی نمی‌شود؛ محتوا فقط از صوت ویدئو استخراج می‌شود.

## نیازمندی‌ها

- Python 3.10 یا جدیدتر
- `ffmpeg` و `ffprobe`
- [Ollama](https://ollama.com/) برای ویرایش محلی
- فضای کافی برای مدل Whisper و مدل زبانی محلی

هیچ `OPENAI_API_KEY` یا Secret پولی لازم نیست.

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

برای نمایش آدرس صفحهٔ اصلی در فایل نهایی، در حالی که دانلود از لینک مستقیم ویدئو انجام می‌شود:

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
└── final/
    ├── transcript.final.md
    ├── transcript.final.txt
    └── editorial-report.json
```

فایل‌های اصلی قابل تحویل:

```text
outputs/<job-id>/final/transcript.final.md
outputs/<job-id>/final/transcript.final.txt
```

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

در این حالت، فایل نهایی همان نسخهٔ ماشینی است و در `result.json` با وضعیت `machine_only` ثبت می‌شود.

## GitHub Actions

Workflow با نام **Process video URL**:

1. ویدئو و صوت را پردازش می‌کند.
2. مدل Whisper را روی CPU اجرا می‌کند.
3. Ollama و مدل `qwen2.5:7b` را داخل همان runner نصب و اجرا می‌کند.
4. بستهٔ کامل خروجی را به‌صورت Artifact تحویل می‌دهد.

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
  "editorial_model": "qwen2.5:7b"
}
```

## اصول ویرایش

- معنا و ترتیب گفت‌وگو حفظ می‌شود.
- نام، عدد، نقل‌قول یا ادعای تازه افزوده نمی‌شود.
- تکرارهای ماشینی و کلمات پرکننده حذف می‌شوند.
- متن موضوع‌بندی و گویندگان تفکیک می‌شوند.
- عبارت غیرقابل‌بازیابی با `[نامفهوم]` مشخص می‌شود.
- برای نقل‌قول کلمه‌به‌کلمه، تطبیق نهایی با صوت همچنان لازم است.

## تست

```bash
ruff check src tests
python -m unittest discover -s tests -v
python -m compileall -q src tests
```
