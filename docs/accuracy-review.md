# Multi-pass ASR Accuracy Review

نسخه `0.7.0` پیش از ویرایش متنی، چند خروجی مستقل از صوت می‌سازد و فقط بر اساس توافق آن‌ها متن اجماعی تولید می‌کند.

## حالت‌ها

```text
off       فقط خروجی اصلی؛ بدون اجرای اضافه
fast      خروجی اصلی + بازخوانی هدفمند بخش‌های مشکوک
balanced  خروجی اصلی + اجرای کامل بدون VAD + بازخوانی هدفمند
maximum   خروجی اصلی + دو اجرای کامل متفاوت + بازخوانی هدفمند
```

حالت پیش‌فرض اجرای `vid-pipeline` برابر `balanced` است.

```bash
VID_PIPELINE_ACCURACY_MODE=balanced vid-pipeline run-url 'VIDEO_URL'
```

برای اجرای مستقل روی یک job موجود:

```bash
vid-accuracy build outputs/<job-id> \
  --mode maximum \
  --model large-v3-turbo \
  --device cpu \
  --compute-type int8 \
  --glossary glossaries/persian-transcript.json
```

## خروجی‌ها

```text
outputs/<job-id>/accuracy/
├── manifest.json
├── passes/
├── clips/
├── disagreements.json
├── review.html
├── corrections.template.json
├── transcript.consensus.json
├── transcript.consensus.md
├── transcript.consensus.txt
├── transcript.consensus.srt
└── transcript.consensus.vtt
```

نام‌ها و اعداد فقط وقتی خودکار تغییر می‌کنند که حداقل دو اجرای مستقل روی یک شکل توافق داشته باشند. در غیر این صورت متن اصلی نگه داشته شده و مورد وارد `disagreements.json` می‌شود.

## بازبینی اختلاف‌ها

```bash
vid-accuracy review outputs/<job-id>
```

سپس فایل زیر را در مرورگر باز کنید:

```text
outputs/<job-id>/accuracy/review.html
```

بعد از تعیین همه موارد و دریافت `accuracy-corrections.json`:

```bash
vid-accuracy apply-review outputs/<job-id> accuracy-corrections.json \
  --reviewer 'نام بازبین'
```

## ارزیابی واقعی

برای سنجش کیفیت، یک قسمت از صوت باید توسط انسان کلمه‌به‌کلمه تصحیح شود:

```bash
vid-accuracy evaluate reference.human.txt transcript.consensus.txt \
  --output accuracy/evaluation.json
```

گزارش شامل `WER` و `CER` است. درصدهای تقریبی بدون متن مرجع انسانی معیار قابل اعتماد نیستند.

## واژه‌نامه یادگیرنده

بعد از اصلاحات انسانی مرحله Review:

```bash
vid-accuracy learn-glossary outputs/<job-id> corrections.json
```

خروجی در مسیر زیر ذخیره می‌شود:

```text
outputs/<job-id>/human/learned-glossary.json
```

این فایل را می‌توان به اجرای ویدیوهای بعدی با `--glossary` یا متغیر `VID_PIPELINE_GLOSSARIES` داد.

## WhisperX

نصب:

```bash
pip install -e '.[alignment]'
```

اجرا:

```bash
vid-accuracy build outputs/<job-id> --mode maximum --whisperx
```

برای فارسی، WhisperX از مدل alignment مخصوص زبان استفاده می‌کند. اگر مدل یا وابستگی در دسترس نباشد، خروجی consensus حفظ شده و خطا فقط در `warnings` ثبت می‌شود.

## تشخیص گوینده

نصب:

```bash
pip install -e '.[diarization]'
```

تشخیص گوینده با `pyannote/speaker-diarization-community-1` انجام می‌شود. حساب Hugging Face باید به مدل دسترسی داشته باشد و توکن از `VID_PIPELINE_PYANNOTE_TOKEN` یا `HF_TOKEN` خوانده می‌شود:

```bash
vid-accuracy build outputs/<job-id> --diarize
```

این قابلیت اختیاری است و در حالت غیرالزامی، خطای دسترسی مدل یا inference باعث حذف متن نمی‌شود.

## متغیرهای اجرای خودکار

```text
VID_PIPELINE_ACCURACY_MODE
VID_PIPELINE_ACCURACY_MODEL
VID_PIPELINE_ACCURACY_DEVICE
VID_PIPELINE_ACCURACY_COMPUTE_TYPE
VID_PIPELINE_ACCURACY_BEAM_SIZE
VID_PIPELINE_TARGETED_BEAM_SIZE
VID_PIPELINE_ACCURACY_CLIP_CONTEXT
VID_PIPELINE_MAX_TARGETED_SEGMENTS
VID_PIPELINE_WHISPERX_ALIGNMENT
VID_PIPELINE_WHISPERX_MODEL
VID_PIPELINE_DIARIZATION
VID_PIPELINE_DIARIZATION_CACHE
```

اگر Accuracy شکست بخورد، خروجی ایمن قبلی حفظ می‌شود. برای اجباری‌کردن موفقیت این مرحله:

```bash
VID_PIPELINE_ACCURACY_REQUIRED=1 vid-pipeline run-url 'VIDEO_URL'
```
