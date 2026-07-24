"""Human-facing Markdown, HTML and assistant-package rendering."""

from __future__ import annotations

import html
from typing import Any

from vid_pipeline.review_types import normalize_text


def assistant_chunks(segments: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flagged = {int(item["segment_id"]): item["id"] for item in items}
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    chars = 0
    for index, segment in enumerate(segments):
        segment_id = int(segment.get("id", index))
        text = normalize_text(str(segment.get("text") or "")) or "[نامفهوم]"
        current.append(
            {
                "segment_id": segment_id,
                "start": float(segment.get("start", 0.0) or 0.0),
                "end": float(segment.get("end", 0.0) or 0.0),
                "text": text,
                "review_item_id": flagged.get(segment_id),
            }
        )
        chars += len(text)
        if chars >= 2500:
            chunks.append({"id": len(chunks) + 1, "start": current[0]["start"], "end": current[-1]["end"], "segments": current})
            current, chars = [], 0
    if current:
        chunks.append({"id": len(chunks) + 1, "start": current[0]["start"], "end": current[-1]["end"], "segments": current})
    return chunks


def review_markdown(manifest: dict[str, Any], items: list[dict[str, Any]]) -> str:
    lines = [
        "# بسته بازبینی انسانی رونویسی", "",
        f"- وضعیت: `{manifest['status']}`",
        f"- تعداد segmentها: {manifest['segment_count']}",
        f"- موارد اجباری: {manifest['required_item_count']}", "",
        "> هر مورد را با صوت تأیید، رد یا اصلاح کنید. پیشنهاد ماشینی به‌تنهایی تأیید انسانی نیست.", "",
    ]
    for item in items:
        lines += [
            f"## {item['id']} — {item['start']:.2f} تا {item['end']:.2f}", "",
            f"- علت‌ها: {', '.join(item['reasons'])}",
            f"- اطمینان میانگین: {item['mean_word_confidence']}",
            f"- کلیپ: `{item.get('clip') or 'تولید نشده'}`", "",
            "**Whisper:**", "", item["source_text"], "",
            "**پیشنهاد کنترل‌شده:**", "", item["proposed_text"], "",
        ]
        if item.get("retranscription"):
            lines += ["**بازشنوی خودکار مجدد:**", "", item["retranscription"]["text"], ""]
    return "\n".join(lines).rstrip() + "\n"


def review_html(manifest: dict[str, Any], items: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for item in items:
        audio = f'<audio controls src="{html.escape(item["clip"])}"></audio>' if item.get("clip") else "<em>کلیپ تولید نشده</em>"
        second = ""
        if item.get("retranscription"):
            second = f'<p><b>بازشنوی دوم:</b> {html.escape(item["retranscription"]["text"])}</p>'
        cards.append(
            f'<section class="card" data-id="{item["id"]}" data-segment-id="{item["segment_id"]}">'
            f'<h2>{item["id"]} — {item["start"]:.2f} تا {item["end"]:.2f}</h2>'
            f'<p><b>علت:</b> {html.escape(", ".join(item["reasons"]))}</p>{audio}'
            f'<label>Whisper</label><textarea readonly>{html.escape(item["source_text"])}</textarea>'
            f'<label>پیشنهاد</label><textarea readonly>{html.escape(item["proposed_text"])}</textarea>{second}'
            '<label>تصمیم</label><select class="decision"><option value="pending">انتخاب نشده</option>'
            '<option value="accept_original">تأیید اصلی</option><option value="accept_suggestion">تأیید پیشنهاد</option>'
            '<option value="edit">ویرایش انسانی</option><option value="unclear">نامفهوم</option></select>'
            f'<label>اصلاح انسانی</label><textarea class="replacement">{html.escape(item["proposed_text"])}</textarea></section>'
        )
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>بازبینی رونویسی</title><style>body{{font-family:sans-serif;max-width:1000px;margin:auto;padding:24px;background:#f6f7f9;line-height:1.8}}.card,.summary{{background:white;border:1px solid #ddd;border-radius:12px;padding:16px;margin:16px 0}}.summary{{position:sticky;top:0;z-index:2}}textarea{{width:100%;min-height:90px;box-sizing:border-box;margin:6px 0 12px;font:inherit}}select,input,button{{font:inherit;padding:8px;margin:6px}}audio{{width:100%}}</style></head><body><h1>بازبینی انسانی رونویسی</h1><div class="summary">موارد اجباری: {manifest['required_item_count']}<br><label>نام بازبین <input id="reviewer"></label><button onclick="save()">دانلود corrections.json</button></div>{''.join(cards)}<script>function save(){{const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){{alert('نام بازبین را وارد کنید');return}}const items=[...document.querySelectorAll('.card')].map(c=>({{id:c.dataset.id,segment_id:Number(c.dataset.segmentId),decision:c.querySelector('.decision').value,replacement:c.querySelector('.replacement').value.trim()}}));const data={{schema_version:1,reviewer,reviewed_at:new Date().toISOString(),items}};const b=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='corrections.json';a.click();URL.revokeObjectURL(a.href)}}</script></body></html>'''
