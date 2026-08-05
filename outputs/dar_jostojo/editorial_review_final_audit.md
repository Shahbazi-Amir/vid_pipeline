# Audit نهایی بازبینی انسانی Transcriptهای فارسی

- Total V2 sessions: 33
- Reviewed TXT count: 33
- Reviewed Markdown count: 33
- Structural failures: none
- Source files modified: 0
- Source files deleted: 0
- Source files renamed: 0
- Sessions rechecked: session-03, session-04, session-10, session-17, session-38, session-40, session-41
- Sessions updated: none
- Mechanical content-rewrite script used: false

## Unresolved passages

- `session-03`: بازه‌های کم‌اعتماد 00:22 تا 00:42 و 01:49 تا 02:23. منابع متنی بازیابی دقیق‌تری فراهم نمی‌کنند و صوت یا ویدئوی محلی موجود نیست.
- `session-04`: بازه کم‌اعتماد و چندزبانه تقریباً 01:07 تا 03:13، به‌ویژه 01:18 تا 02:45. منابع موجود برای بازسازی دقیق کافی نیستند.
- `session-10`: بازه کم‌اعتماد و چندزبانه تقریباً 00:52 تا 01:22. جزئیات حذف‌شده به‌طور مستقل در منابع موجود تأیید نمی‌شوند.
- `session-17`: بازه کم‌اعتماد و چندزبانه تقریباً 06:19 تا 07:17. جزئیات گفتار از منابع متنی قابل‌بازیابی دقیق نیست.
- `session-38`: عبارت «ذَهابَک، ذَهَبَک و مذهبَک» با توضیح فارسی پس از آن سازگار است، اما ASR این قسمت مخدوش است و صدای محلی برای تأیید ضبط و حرکت‌گذاری دقیق وجود ندارد؛ بنابراین قطعی گزارش نمی‌شود.

## Sensitive names/numbers verified

- `session-40`: قانون موریل؛ آبراهام لینکلن؛ Jump$tart؛ ۳۶ موضوع؛ ۱۲۷ مفهوم جزئی؛ ۳۸۱ مؤلفه. این موارد با گفتار و بافت همان Session سازگارند؛ Jump$tart چند بار تکرار شده و ۳۸۱ مؤلفه نیز از سه بُعد برای ۱۲۷ مفهوم در همان گفتار توضیح داده شده است.
- `session-41`: «سازمان همکاری و توسعه اقتصادی (OECD)». کاربرد آن در Session، پرسش‌نامه ترکیبی سنجش دانش، مهارت و نگرش مالی است.

## Batch commit mapping

| Commit SHA | Sessions |
|---|---|
| `8f22ea65ceca3586490093bc3924b69a71505e0c` | session-01, session-02, session-03 |
| `332f7677151b413a04e4a2ffbabc508b2ef2b301` | session-04, session-05, session-06 |
| `3a5c0a020adf9a12196ad77d98073d1fd91b5e41` | session-07, session-08, session-09 |
| `fe211385b0c7f7c865bfc5f836ad16f44fe2853d` | session-10, session-12, session-14 |
| `a4ed6284667ffa8a47d324834f64a61bf6cb76cc` | session-15, session-16, session-17 |
| `a4daba40fb2a160643216dac46114976ad384069` | session-18, session-20, session-21 |
| `74704a9dbb92a4ba330fe8a699d804e4cbc4bd99` | session-22, session-23, session-25 |
| `c3c37cc7a76c194aedcef2547dda927361393660` | session-26, session-27, session-28 |
| `9035d195e1997e9e22fd350f76f06c418f827b33` | session-30, session-31, session-32 |
| `9c58a6210544756c2a0dc5268309a2dd3d71bf0a` | session-33, session-35, session-37 |
| `c72307f58f50ff00a3881de45c1674cbc2ec4c90` | session-38, session-40, session-41 |

## Structural validation

هر ۳۳ Session دارای یک TXT و یک Markdown بازبینی‌شده و غیرخالی است. همه فایل‌ها UTF-8 معتبرند و با یک Newline پایان می‌یابند. بدنه هر Markdown پس از عنوان دقیقاً با TXT متناظر برابر است. هیچ فایل داخل `final` تغییر نکرده و فایل موقتی باقی نمانده است.
