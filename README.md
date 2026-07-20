# Financial Video RAG Pipeline

پایپ‌لاین ماژولار برای دریافت ویدئوهای آکادمی هوش مالی، استخراج و استانداردسازی صوت، تولید متن فارسی زمان‌دار، آماده‌سازی بازبینی انسانی و ساخت خروجی سازگار با مخزن [`Shahbazi-Amir/transcription`](https://github.com/Shahbazi-Amir/transcription).

## هدف

این مخزن کد و ابزار پردازش را نگهداری می‌کند. فایل‌های نهایی هر قسمت پس از بازبینی واقعی در branch زیر از مخزن مقصد منتشر می‌شوند:

```text
agent/financial-rag-transcripts
```

مسیر کلی:

```text
URL یا جست‌وجوی محدود در سایت
→ اعتبارسنجی منبع
→ دانلود با yt-dlp
→ استخراج صوت با ffmpeg
→ mono / 16kHz WAV
→ faster-whisper فارسی با timestamp
→ فایل بازبینی و علامت‌گذاری بخش‌های مشکوک
→ تأیید انسانی تطابق با صوت
→ Markdown نهایی
→ JSONL مخصوص RAG
→ commit و push امن به مخزن مقصد
```

## اصول مهم

- دانلود، صوت، رونویسی، بازبینی، RAG و انتشار ماژول‌های جدا هستند.
- وضعیت هر مرحله در `state.json` ذخیره می‌شود تا اجرای قطع‌شده از ابتدا شروع نشود.
- ویدئو، صوت و مدل‌ها وارد Git نمی‌شوند.
- خروجی Whisper متن نهایی نیست.
- وضعیت `reviewed` فقط با فلگ صریح `--confirm-audio-reviewed` و ثبت checksum صوت و متن ایجاد می‌شود.
- اگر متن پس از تأیید تغییر کند، ساخت RAG متوقف می‌شود تا دوباره بازبینی شود.
- انتشار فقط از branch `agent/financial-rag-transcripts` و روی working tree تمیز انجام می‌شود.

## نیازمندی‌ها

- Python 3.10 یا جدیدتر
- `ffmpeg` و `ffprobe`
- برای دانلود: `yt-dlp`
- برای رونویسی: `faster-whisper`

### macOS

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
```

MacBook Pro 2015 برای تست و مدل‌های کوچک مناسب است. برای پردازش کامل، Colab رایگان با GPU در صورت موجود بودن سریع‌تر است.

## شروع یک قسمت

نمونهٔ آماده:

```text
examples/asre-shirin-season-2-episode-01.json
```

یا ساخت فایل جدید:

```bash
vid-pipeline init episodes/episode-01.json \
  --program 'عصر شیرین' \
  --collection asre-shirin-season-2 \
  --season 'فصل دوم' \
  --season-episode 1 \
  --overall-episode 14 \
  --speaker 'دکتر کمیل رودی' \
  --additional-speaker 'مجری برنامه'
```

## کشف منبع

جست‌وجو از sitemap سایت انجام می‌شود و به سرویس پولی وابسته نیست:

```bash
vid-pipeline discover \
  --site https://www.fintelligence.ir/ \
  --query 'عصر شیرین قسمت ۱۴ کمیل رودی' \
  --output candidates.json
```

خروجی را بررسی و URL قطعی صفحه و ویدئو را در فایل قسمت ثبت کنید. پس از بررسی دستی شماره قسمت، منبع و حضور دکتر کمیل رودی، این دو مقدار را در فایل JSON برابر `true` قرار دهید:

```json
"source_verified": true,
"speaker_verified": true
```

تا قبل از این تأییدها مرحله دانلود عمداً متوقف می‌شود. عنوان، شماره و حضور سخنران نباید حدس زده شوند.

برای بررسی مستقیم یک صفحه یا ویدئو:

```bash
vid-pipeline inspect-source 'https://www.aparat.com/v/VIDEO_ID'
```

## اجرای خودکار تا مرحلهٔ بازبینی

```bash
vid-pipeline run episodes/episode-01.json \
  --work-root work \
  --model small \
  --device auto
```

خروجی‌ها در این ساختار ایجاد می‌شوند:

```text
work/<collection>/episode-01/
├── state.json
├── source.json
├── video-info.json
├── video/
├── audio/audio-16k-mono.wav
├── raw/episode-01.raw.json
├── raw/episode-01.raw.md
├── review/episode-01.review.md
├── final/episode-01.md
└── rag/<collection>-episode-01.jsonl
```

وضعیت:

```bash
vid-pipeline status episodes/episode-01.json --work-root work
```

## بازبینی انسانی

فایل `review/*.review.md` را همراه صوت گوش دهید و نسخهٔ اصلاح‌شده را در فایل جدا ذخیره کنید. سپس:

```bash
vid-pipeline mark-reviewed episodes/episode-01.json \
  --work-root work \
  --transcript reviewed-episode-01.md \
  --reviewer 'Amir Shahbazi' \
  --confirm-audio-reviewed
```

این فرمان متن را در مسیر نهایی کپی و رسید بازبینی دارای checksum ایجاد می‌کند. `[نامفهوم]` برای بخش واقعاً غیرقابل‌تشخیص مجاز است.

## ساخت و اعتبارسنجی RAG

```bash
vid-pipeline build-rag episodes/episode-01.json --work-root work
vid-pipeline validate-rag work/asre-shirin-season-2/episode-01/rag/asre-shirin-season-2-episode-01.jsonl
```

فرمت هر خط:

```json
{
  "id": "asre-shirin-season-2-01-001",
  "text": "...",
  "metadata": {
    "program": "عصر شیرین",
    "season": "فصل دوم",
    "episode": 1,
    "overall_episode": 14,
    "title": "...",
    "speakers": ["دکتر کمیل رودی"],
    "source_url": "...",
    "video_url": "...",
    "language": "fa",
    "review_status": "reviewed"
  }
}
```

## انتشار در مخزن transcription

ابتدا مخزن مقصد را روی branch درست checkout کنید و مطمئن شوید تغییر دیگری ندارد:

```bash
git -C ../transcription checkout agent/financial-rag-transcripts
git -C ../transcription pull --ff-only
```

سپس:

```bash
vid-pipeline publish episodes/episode-01.json \
  --work-root work \
  --destination-repo ../transcription \
  --branch agent/financial-rag-transcripts \
  --push
```

فرمان انتشار:

- رسید بازبینی و checksum متن را کنترل می‌کند.
- JSONL را اعتبارسنجی می‌کند.
- فایل‌های `sources`، `raw`، `transcripts` و `rag/episodes` را کپی می‌کند.
- `manifest.json` را به‌روزرسانی می‌کند.
- برای همان قسمت commit جدا می‌سازد.
- فقط در صورت `--push` به GitHub پوش می‌کند.

## Google Colab رایگان

Notebook زیر نصب، اتصال Drive و اجرای پایپ‌لاین را آماده می‌کند:

```text
notebooks/financial_video_rag_colab.ipynb
```

Colab رایگان تضمین دائمی GPU یا session بدون قطع ندارد. ذخیرهٔ `work/` در Google Drive باعث می‌شود بعد از قطع session مراحل تکمیل‌شده دوباره اجرا نشوند.

## اجرای تست‌ها

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

در GitHub Actions نیز تست‌ها و بررسی Ruff روی هر push و pull request اجرا می‌شوند.

## ساختار کد

```text
src/vid_pipeline/
├── source.py       کشف و اعتبارسنجی منبع
├── download.py     دانلود و metadata با yt-dlp
├── audio.py        ffmpeg و کنترل mono/16kHz
├── transcribe.py   faster-whisper و timestamp
├── review.py       بسته و رسید بازبینی
├── rag.py          chunking و JSONL
├── state.py        ادامهٔ پردازش و checksum
├── pipeline.py     هماهنگی مراحل خودکار
├── publish.py      commit/push امن به مقصد
└── cli.py          رابط خط فرمان
```

## محدودیت صداقت بازبینی

این ابزار می‌تواند بخش‌های کم‌اعتماد، سکوت و تکرار احتمالی را علامت بزند؛ اما نمی‌تواند بدون گوش‌دادن واقعی ادعا کند متن کاملاً با ویدئو تطبیق داده شده است. مرحلهٔ نهایی بازبینی انسانی عمداً اجباری است.
