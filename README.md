# Video Transcript Pipeline

یک پایپ‌لاین مستقل برای تبدیل **یک لینک ویدئو** به متن فارسی خام، متن پاک‌سازی‌شدۀ ماشینی و متن نهاییِ ویرایش‌شدۀ هوشمند.

## مسیر کامل پردازش

```text
Video URL
→ بررسی منبع و دانلود با yt-dlp
→ استخراج و استانداردسازی صوت با ffmpeg
→ رونویسی زمان‌دار با faster-whisper
→ پاک‌سازی قطعی و حذف تکرارهای آشکار
→ بازسازی معنایی چندمرحله‌ای با مدل زبانی
→ گوینده‌بندی و موضوع‌بندی
→ خروجی نهایی Markdown و TXT
```

نسخۀ خام و نسخۀ ماشینی حذف نمی‌شوند؛ بنابراین می‌توان خروجی نهایی را با منبع اولیه کنترل کرد.

## نیازمندی‌ها

- Python 3.10 یا جدیدتر
- `ffmpeg` و `ffprobe`
- فضای کافی برای ویدئو و صوت
- متغیر محیطی `OPENAI_API_KEY` برای مرحلۀ ویرایش نهایی

### نصب

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
```

## اجرای کامل با یک لینک

```bash
export OPENAI_API_KEY='...'

vid-pipeline run-url 'https://example.com/video' \
  --language fa \
  --model large-v3-turbo \
  --editorial-model gpt-5
```

در حالت عادی عنوان، مدت و ناشر از خود لینک استخراج می‌شوند. برای افزایش دقت نام‌ها و قالب نهایی می‌توان اطلاعات تکمیلی داد:

```bash
vid-pipeline run-url 'https://example.com/video' \
  --name interview-01 \
  --title 'عنوان گفت‌وگو' \
  --program 'نام برنامه' \
  --network 'نام شبکه' \
  --date '۱۴۰۵/۰۴/۱۶' \
  --guest 'نام مهمان' \
  --speaker 'مجری' \
  --speaker 'مهمان' \
  --editorial-context 'موضوع اصلی و نام‌های خاص برنامه'
```

## خروجی

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
├── machine/
│   ├── transcript.machine.md
│   └── transcript.machine.txt
└── final/
    ├── transcript.final.md
    ├── transcript.final.txt
    └── editorial-report.json
```

فایل اصلی قابل تحویل:

```text
outputs/<job-id>/final/transcript.final.md
```

این فایل شامل عنوان، مشخصات منبع، تیترهای موضوعی، تفکیک گویندگان و متن فارسی بازسازی‌شده است.

## ویرایش یک رونویسی موجود

اگر فایل JSON خام Whisper از قبل موجود است، نیازی به دانلود و رونویسی دوباره نیست:

```bash
export OPENAI_API_KEY='...'

vid-pipeline edit transcript.raw.json \
  --markdown transcript.final.md \
  --text transcript.final.txt \
  --title 'عنوان ویدئو' \
  --source-url 'https://example.com/video' \
  --guest 'نام مهمان'
```

## اجرای بدون ویرایش هوشمند

برای عیب‌یابی یا اجرای کاملاً آفلاین:

```bash
vid-pipeline run-url 'https://example.com/video' --no-editorial
```

در این حالت فایل `final/` فقط نسخۀ ماشینی است و در `result.json` با وضعیت `machine_only` مشخص می‌شود.

## GitHub Actions

Workflow با نام **Process video URL** از بخش Actions قابل اجراست. لینک ویدئو و اطلاعات اختیاری را وارد کنید؛ پس از پایان، پوشۀ کامل خروجی به‌صورت Artifact قابل دانلود است.

برای فعال‌بودن ویرایش نهایی، secret زیر را در مخزن تعریف کنید:

```text
OPENAI_API_KEY
```

## اصول ویرایش هوشمند

- معنا و ترتیب گفت‌وگو حفظ می‌شود.
- خطاهای آوایی و دستوری فقط با اتکا به بافت اصلاح می‌شوند.
- نام، عدد، آیه یا ادعای تازه افزوده نمی‌شود.
- تکرارهای ماشینی و کلمات پرکننده حذف می‌شوند.
- گویندگان تفکیک و متن موضوع‌بندی می‌شود.
- عبارت غیرقابل‌بازیابی با `[نامفهوم]` مشخص می‌شود.
- برای نقل‌قول حقوقی، علمی یا سیاسیِ کلمه‌به‌کلمه، تطبیق نهایی با صوت همچنان لازم است.

## مشاهدهٔ وضعیت و اجرای مجدد

```bash
vid-pipeline status <job-id> --output-root outputs
vid-pipeline run-url 'https://example.com/video' --force
```

## بررسی لینک بدون دانلود

```bash
vid-pipeline inspect 'https://example.com/video'
```

## تست و کیفیت کد

```bash
ruff check src tests
python -m unittest discover -s tests -v
python -m compileall -q src tests
```
