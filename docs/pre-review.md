# خروجی کامل زمان‌دار پیش از بازبینی

از نسخه `0.6.1`، پایپ‌لاین بلافاصله پس از پایان پردازش اصلی و پیش از ساخت بسته بازبینی انسانی، یک نسخه مستقل و بدون تغییر از خروجی Whisper می‌سازد.

این نسخه برای مواقعی است که بخواهیم در آینده متن را با روش دیگری بازبینی کنیم، مدل دیگری روی آن اجرا کنیم یا هر بخش را مستقیماً با صوت تطبیق دهیم.

## اصل مهم

فایل‌های `pre_review/` فقط از `raw/transcript.raw.json` ساخته می‌شوند:

- هیچ متن خارجی یا متن صفحه منبع وارد نمی‌شود.
- هیچ جمله‌ای حذف، خلاصه یا بازنویسی نمی‌شود.
- ترتیب همه segmentها حفظ می‌شود.
- زمان شروع و پایان هر segment حفظ می‌شود.
- در صورت وجود word timestamps، زمان و confidence تک‌تک کلمات نیز حفظ می‌شود.
- شاخص‌های `avg_logprob`، `no_speech_prob`، `compression_ratio` و `review_flags` ثبت می‌شوند.

زمان‌های Whisper هم‌ترازی مدل هستند و برای انتشار حساس همچنان باید با صوت تأیید شوند.

## فایل‌های خروجی

```text
outputs/<job-id>/pre_review/
├── manifest.json
├── transcript.pre-review.txt
├── transcript.pre-review.md
├── transcript.pre-review.json
├── transcript.pre-review.srt
└── transcript.pre-review.vtt
```

### فایل اصلی متنی

```text
pre_review/transcript.pre-review.txt
```

نمونه ساختار:

```text
[SEGMENT 0003] [00:00:00.210 --> 00:00:02.100]
مدت بخش: 1.890 ثانیه
avg_logprob: -0.250000
no_speech_prob: 0.010000
پرچم‌های بازبینی: low_word_confidence
متن:
سلام دنیا

کلمات زمان‌دار:
  00:00:00.210 --> 00:00:00.800 | سلام | confidence=0.9100
  00:00:00.800 --> 00:00:01.400 | دنیا | confidence=0.7300
```

### JSON کامل

`transcript.pre-review.json` نسخه ساختاریافته کامل است و همه اطلاعات خام Whisper را در کلید `transcription` نگه می‌دارد. این فایل مناسب پردازش مجدد، RAG، مدل دوم، رابط بازبینی دیگر یا تحلیل کیفیت است.

### SRT و VTT

فایل‌های SRT و VTT همان متن قبل از بازبینی را با زمان segmentها ارائه می‌کنند و برای پخش ویدئو یا ابزارهای زیرنویس مناسب‌اند.

## اجرای خودکار

فرمان عادی زیر، pre-review و سپس review را خودکار تولید می‌کند:

```bash
vid-pipeline run-url 'VIDEO_URL' ...
```

## تولید مجدد فقط این مرحله

```bash
vid-review pre-review outputs/<job-id>
```

## ساخت هم‌زمان pre-review و بسته بازبینی انسانی

```bash
vid-review build outputs/<job-id>
```

## ترتیب نسخه‌ها

```text
raw/transcript.raw.json
        ↓
pre_review/transcript.pre-review.*   ← نسخه کامل زمان‌دار و بدون تغییر
        ↓
machine/ و final/                    ← پاک‌سازی و ویرایش ماشینی
        ↓
review/                               ← پیشنهادها، کلیپ‌ها و تصمیم‌های بازبین
        ↓
human/                                ← نسخه تأییدشده انسانی
```
