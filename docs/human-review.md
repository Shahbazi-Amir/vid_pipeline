# مرحله بازبینی انسانی و کنترل نهایی

از نسخه `0.6.0`، فرمان اصلی `vid-pipeline run-url` پس از تولید متن، به‌صورت خودکار بسته بازبینی زیر را می‌سازد:

```text
outputs/<job-id>/review/
├── manifest.json
├── uncertain-spans.json
├── editorial-audit.json
├── quality-report.json
├── assistant-review-package.json
├── transcript.review.srt
├── transcript.review.vtt
├── review.md
├── review.html
├── corrections.template.json
└── clips/
```

یک نسخه ZIP نیز در مسیر زیر قرار می‌گیرد تا Workflow فعلی GitHub آن را همراه خروجی نهایی منتشر کند:

```text
outputs/<job-id>/final/review-package.zip
```

این مرحله هیچ متن خارجی را وارد خروجی نمی‌کند و هیچ پیشنهاد ماشینی را به‌عنوان حقیقت قطعی نمی‌پذیرد.

## کارهایی که مرحله Review انجام می‌دهد

- واژه‌ها و segmentهای کم‌اعتماد Whisper را پیدا می‌کند.
- نام اشخاص، عنوان‌ها، اعداد، درصدها و عبارت‌های عربی یا قرآنی را علامت می‌زند.
- واژه‌های مشکوک را با واژه‌نامه‌های محلی مقایسه می‌کند.
- برای هر segment مشکوک، کلیپ صوتی کوتاه تولید می‌کند.
- در صورت تنظیم مدل بازشنوی، همان کلیپ‌ها را با Whisper دوم دوباره رونویسی می‌کند.
- اختلاف متن machine و editorial را بدون تغییر متن گزارش می‌کند.
- برای هر segment و هر بلوک زمانی امتیاز کیفیت تولید می‌کند.
- خروجی زمان‌دار SRT و VTT می‌سازد.
- یک صفحه HTML برای گوش‌دادن، تأیید یا اصلاح هر مورد می‌سازد.
- یک بسته JSON مناسب بازبینی توسط دستیار یا ابزارهای دیگر تولید می‌کند.
- تا وقتی همه موارد اجباری تعیین تکلیف نشوند، وضعیت را `human_review_required` نگه می‌دارد.

## اجرای دستی

```bash
vid-review build outputs/<job-id> \
  --glossary glossaries/persian-transcript.json
```

برای بازشنوی خودکار دوباره فقط بخش‌های مشکوک:

```bash
vid-review build outputs/<job-id> \
  --glossary glossaries/persian-transcript.json \
  --retranscribe-model large-v3-turbo \
  --device cpu \
  --compute-type int8
```

## بازبینی انسانی

فایل زیر را در مرورگر باز کنید:

```text
outputs/<job-id>/review/review.html
```

برای هر مورد یکی از تصمیم‌های زیر ثبت می‌شود:

- `accept_original`: بازبین صوت را شنیده و متن Whisper را تأیید کرده است.
- `accept_suggestion`: بازبین پیشنهاد کنترل‌شده واژه‌نامه را تأیید کرده است.
- `edit`: بازبین متن را دستی اصلاح کرده است.
- `unclear`: بازبین صوت را شنیده اما عبارت قابل بازیابی نیست؛ در خروجی `[نامفهوم]` ثبت می‌شود.

صفحه HTML فایل `corrections.json` را دانلود می‌کند.

## تولید متن تأییدشده انسانی

```bash
vid-review apply outputs/<job-id> corrections.json \
  --reviewer 'نام بازبین' \
  --promote
```

اگر حتی یک مورد اجباری بدون تصمیم باقی مانده باشد، فرمان شکست می‌خورد و فایل نهایی به وضعیت `human_verified` ارتقا پیدا نمی‌کند.

خروجی‌های انسانی:

```text
outputs/<job-id>/human/transcript.human.txt
outputs/<job-id>/human/transcript.human.md
outputs/<job-id>/human/transcript.human.srt
outputs/<job-id>/human/transcript.human.vtt
outputs/<job-id>/human/verification.json
```

با `--promote` همین نسخه به مسیرهای `final/transcript.final.*` منتقل و `result.json` با مقادیر زیر ثبت می‌شود:

```json
{
  "status": "completed",
  "review_status": "human_verified",
  "human_audio_verification": true
}
```

## متغیرهای محیطی اجرای خودکار

```text
VID_PIPELINE_GLOSSARIES
VID_PIPELINE_GLOSSARY_DIR
VID_PIPELINE_REVIEW_CONFIDENCE
VID_PIPELINE_REVIEW_LOGPROB
VID_PIPELINE_REVIEW_CLIP_CONTEXT
VID_PIPELINE_REVIEW_CLIPS
VID_PIPELINE_RETRANSCRIBE_MODEL
VID_PIPELINE_RETRANSCRIBE_DEVICE
VID_PIPELINE_RETRANSCRIBE_COMPUTE_TYPE
```

`VID_PIPELINE_GLOSSARIES` چند مسیر را با جداکننده مسیر سیستم‌عامل می‌پذیرد. اگر تنظیم نشود، تمام فایل‌های JSON پوشه `glossaries/` بارگذاری می‌شوند.
