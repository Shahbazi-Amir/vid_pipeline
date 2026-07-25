"""Human resolution of multi-pass ASR disagreements and learned glossary."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from vid_pipeline.accuracy import AccuracyError, key, norm, now, render_outputs


def build_accuracy_review(job_root: str | Path) -> dict[str, Any]:
    root = Path(job_root)
    directory = root / "accuracy"
    source = directory / "disagreements.json"
    if not source.exists():
        raise AccuracyError("accuracy disagreements do not exist")
    items = json.loads(source.read_text(encoding="utf-8")).get("items") or []
    cards = []
    for item in items:
        options = "".join(
            f"<label><input type='radio' name='s{item['segment_id']}' "
            f"value='candidate:{index}'> {html.escape(str(candidate.get('pass')))}: "
            f"{html.escape(str(candidate.get('text')))}</label>"
            for index, candidate in enumerate(item.get("candidates") or [])
        )
        audio = (
            f"<audio controls src='{html.escape(str(item.get('clip')))}'></audio>"
            if item.get("clip")
            else ""
        )
        cards.append(
            f"<section data-id='{item['segment_id']}'>"
            f"<h2>{item['start']:.3f} تا {item['end']:.3f}</h2>{audio}{options}"
            f"<label><input type='radio' name='s{item['segment_id']}' value='edit'>ویرایش</label>"
            f"<textarea id='e{item['segment_id']}'>{html.escape(item.get('selected_text') or '')}</textarea>"
            f"<label><input type='radio' name='s{item['segment_id']}' value='unclear'>نامفهوم</label>"
            "</section>"
        )
    page = (
        "<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'>"
        "<style>body{font-family:sans-serif;max-width:1000px;margin:auto}"
        "section{padding:16px;margin:14px;border:1px solid #ccc}"
        "label{display:block;margin:8px}textarea{width:100%}</style>"
        "<h1>بازبینی اختلاف‌های ASR</h1>"
        + "".join(cards)
        + """<button onclick='save()'>دانلود corrections.json</button>
<script>function save(){let items=[];document.querySelectorAll('section').forEach(s=>{let id=+s.dataset.id,x=document.querySelector(`input[name=s${id}]:checked`),o={segment_id:id,decision:'pending',candidate_index:null,replacement:''};if(x){if(x.value.startsWith('candidate:')){o.decision='candidate';o.candidate_index=+x.value.split(':')[1]}else if(x.value==='edit'){o.decision='edit';o.replacement=document.getElementById(`e${id}`).value}else{o.decision='unclear'}}items.push(o)});let b=new Blob([JSON.stringify({reviewer:'',items},null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='accuracy-corrections.json';a.click()}</script></html>"""
    )
    html_path = directory / "review.html"
    html_path.write_text(page, encoding="utf-8")
    template = directory / "corrections.template.json"
    template.write_text(
        json.dumps(
            {
                "reviewer": "",
                "items": [
                    {
                        "segment_id": item["segment_id"],
                        "decision": "pending",
                        "candidate_index": None,
                        "replacement": item.get("selected_text", ""),
                    }
                    for item in items
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status": "accuracy_review_required" if items else "accuracy_review_optional",
        "items": len(items),
        "review_html": str(html_path),
        "corrections_template": str(template),
    }


def apply_accuracy_review(
    job_root: str | Path,
    corrections: str | Path,
    reviewer: str = "",
) -> dict[str, Any]:
    root = Path(job_root)
    directory = root / "accuracy"
    data = json.loads((directory / "transcript.consensus.json").read_text(encoding="utf-8"))
    disagreements = json.loads(
        (directory / "disagreements.json").read_text(encoding="utf-8")
    ).get("items") or []
    correction_data = json.loads(Path(corrections).read_text(encoding="utf-8"))
    reviewer = norm(reviewer or correction_data.get("reviewer") or "")
    if not reviewer:
        raise AccuracyError("reviewer is required")
    by_id = {int(item["segment_id"]): item for item in disagreements}
    choices = {
        int(item["segment_id"]): item
        for item in correction_data.get("items") or []
        if item.get("segment_id") is not None
    }
    unresolved = []
    for segment_id, item in by_id.items():
        correction = choices.get(segment_id, {})
        decision = correction.get("decision")
        if (
            decision == "candidate"
            and isinstance(correction.get("candidate_index"), int)
            and 0 <= correction["candidate_index"] < len(item.get("candidates") or [])
        ):
            continue
        if decision == "edit" and norm(correction.get("replacement") or ""):
            continue
        if decision == "unclear":
            continue
        unresolved.append(segment_id)
    if unresolved:
        raise AccuracyError("unresolved accuracy items: " + ", ".join(map(str, unresolved)))
    changed = 0
    for segment in data.get("segments") or []:
        segment_id = int(segment.get("id"))
        if segment_id not in by_id:
            continue
        correction = choices[segment_id]
        if correction["decision"] == "candidate":
            text = norm(
                by_id[segment_id]["candidates"][correction["candidate_index"]]["text"]
            )
        elif correction["decision"] == "edit":
            text = norm(correction["replacement"])
        else:
            text = "[نامفهوم]"
        changed += text != segment.get("text")
        segment["text"] = text
        segment.setdefault("consensus", {})["requires_human"] = False
        segment["consensus"]["human_reviewer"] = reviewer
        segment["review_flags"] = [
            flag
            for flag in segment.get("review_flags") or []
            if flag
            not in {
                "multi_pass_disagreement",
                "protected_name_or_number_disagreement",
                "low_consensus_confidence",
            }
        ]
    data["text"] = " ".join(segment["text"] for segment in data.get("segments") or [])
    files = render_outputs(root, data, [])
    report = {
        "status": "accuracy_human_resolved",
        "reviewer": reviewer,
        "reviewed_at": now(),
        "resolved_items": len(by_id),
        "changed_segments": changed,
        "files": files,
    }
    (directory / "human-resolution.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def update_learned_glossary(
    job_root: str | Path,
    corrections: str | Path,
    output: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(job_root)
    uncertain = json.loads(
        (root / "review" / "uncertain-spans.json").read_text(encoding="utf-8")
    )
    source = {
        int(item["segment_id"]): str(item.get("source_text") or "")
        for item in uncertain.get("items") or []
    }
    fixes = json.loads(Path(corrections).read_text(encoding="utf-8"))
    entries: dict[str, dict[str, Any]] = {}
    destination = Path(output) if output else root / "human" / "learned-glossary.json"
    if destination.exists():
        for item in json.loads(destination.read_text(encoding="utf-8")).get("entries") or []:
            entries[key(item.get("canonical") or "")] = item
    for correction in fixes.get("items") or []:
        if correction.get("decision") != "edit":
            continue
        observed = norm(source.get(int(correction["segment_id"]), ""))
        canonical = norm(correction.get("replacement") or "")
        if not observed or not canonical or key(observed) == key(canonical):
            continue
        entry = entries.setdefault(
            key(canonical),
            {"canonical": canonical, "aliases": [], "confirmed_count": 0},
        )
        if observed not in entry["aliases"]:
            entry["aliases"].append(observed)
        entry["confirmed_count"] = int(entry.get("confirmed_count", 0)) + 1
    payload = {
        "schema_version": 1,
        "updated_at": now(),
        "entries": list(entries.values()),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


__all__ = [
    "apply_accuracy_review",
    "build_accuracy_review",
    "update_learned_glossary",
]
