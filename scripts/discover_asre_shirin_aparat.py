from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

CHANNEL = "fintelligence"
CHANNEL_API = f"https://www.aparat.com/etc/api/videoByUser/username/{CHANNEL}/perpage/100"
VIDEO_API = "https://www.aparat.com/etc/api/video/videohash/{uid}"
OUT_JSON = Path("sources/asre_shirin/aparat_manifest.json")
OUT_MD = Path("sources/asre_shirin/links.md")

ORDINALS = {
    "اول": 1,
    "دوم": 2,
    "سوم": 3,
    "چهارم": 4,
    "پنجم": 5,
    "ششم": 6,
    "هفتم": 7,
    "هشتم": 8,
    "نهم": 9,
    "دهم": 10,
    "یازدهم": 11,
    "دوازدهم": 12,
    "سیزدهم": 13,
    "چهاردهم": 14,
    "پانزدهم": 15,
    "شانزدهم": 16,
    "هفدهم": 17,
    "هجدهم": 18,
    "نوزدهم": 19,
    "بیستم": 20,
    "بیست و یکم": 21,
    "بیست و دوم": 22,
    "بیست و سوم": 23,
    "بیست و چهارم": 24,
    "بیست و پنجم": 25,
    "بیست و ششم": 26,
}

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "vid-pipeline-aparat-discovery/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def normalize(text: str) -> str:
    text = str(text or "").translate(PERSIAN_DIGITS)
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
    text = text.replace("\u200c", " ").replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip().casefold()


def flatten_videos(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("videobyuser", "videoByUser", "videos", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        for value in payload.values():
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                return value
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def extract_detail(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        for key in ("video", "videobyhash", "data"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
        return payload
    return {}


def episode_number(text: str) -> int | None:
    value = normalize(text)
    # Prefer an explicit number following the word "episode" (قسمت).
    match = re.search(r"قسمت\s*(?:شماره\s*)?([0-9]{1,2})(?:\D|$)", value)
    if match:
        number = int(match.group(1))
        return number if 1 <= number <= 26 else None

    # Match Persian ordinal words after normalization. Longest first avoids
    # matching "دوم" inside "دوازدهم"-style text accidentally.
    for word, number in sorted(ORDINALS.items(), key=lambda item: len(item[0]), reverse=True):
        compact_pattern = re.escape(word).replace(r"\ ", r"\s*")
        if re.search(rf"قسمت\s*{compact_pattern}(?:\s|$|[،؛:])", value):
            return number
    return None


def is_series_candidate(text: str) -> bool:
    value = normalize(text)
    return (
        "عصر شیرین" in value
        or ("سواد مالی" in value and ("خانم" in value or "کمیل رودی" in value))
    )


def main() -> None:
    channel_payload = fetch_json(CHANNEL_API)
    channel_videos = flatten_videos(channel_payload)
    if not channel_videos:
        raise SystemExit("Aparat channel API returned no videos")

    records: dict[int, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []

    for item in channel_videos:
        uid = str(item.get("uid") or item.get("videohash") or "").strip()
        if not uid:
            continue
        title = str(item.get("title") or "")
        if not is_series_candidate(title):
            continue

        detail: dict[str, Any] = {}
        try:
            detail = extract_detail(fetch_json(VIDEO_API.format(uid=uid)))
        except Exception as exc:  # Keep discovery auditable even if one detail call fails.
            diagnostics.append({"uid": uid, "title": title, "detail_error": type(exc).__name__})

        description = str(
            detail.get("description")
            or detail.get("desc")
            or item.get("description")
            or ""
        )
        combined = " ".join(
            part for part in (
                title,
                str(detail.get("title") or ""),
                description,
                str(detail.get("tags") or ""),
            ) if part
        )
        number = episode_number(combined)
        if number is None:
            diagnostics.append({"uid": uid, "title": title, "reason": "episode_number_unresolved"})
            continue

        username = str(detail.get("username") or item.get("username") or CHANNEL)
        if normalize(username) != normalize(CHANNEL):
            diagnostics.append({"uid": uid, "title": title, "reason": "wrong_channel"})
            continue

        record = {
            "result_number": number,
            "uid": uid,
            "url": f"https://www.aparat.com/v/{uid}",
            "title": str(detail.get("title") or title),
            "description": description,
            "duration": detail.get("duration") or item.get("duration"),
            "sdate": detail.get("sdate") or item.get("sdate") or "",
            "username": username,
        }
        if number in records and records[number]["uid"] != uid:
            raise SystemExit(
                f"Duplicate Aparat candidates resolved to episode {number}: "
                f"{records[number]['uid']} and {uid}"
            )
        records[number] = record

    ordered = [records[number] for number in sorted(records)]
    actual = set(records)
    expected = set(range(1, 27))
    missing = sorted(expected - actual)

    payload = {
        "series": "سواد مالی در عصر شیرین",
        "channel": CHANNEL,
        "channel_url": f"https://www.aparat.com/{CHANNEL}/videos",
        "expected_count": 26,
        "discovered_count": len(ordered),
        "complete": actual == expected,
        "missing_numbers": missing,
        "videos": ordered,
        "diagnostics": diagnostics,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# سواد مالی در عصر شیرین — لینک‌های آپارات",
        "",
        f"- Channel: https://www.aparat.com/{CHANNEL}/videos",
        f"- Expected: 26",
        f"- Discovered: {len(ordered)}",
        f"- Missing: {', '.join(map(str, missing)) if missing else 'none'}",
        "",
    ]
    for row in ordered:
        lines.append(f"{row['result_number']}. [{row['title']}]({row['url']})")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"discovered": len(ordered), "missing": missing}, ensure_ascii=False))
    if missing:
        raise SystemExit(f"Aparat Asre Shirin discovery incomplete; missing episodes: {missing}")


if __name__ == "__main__":
    main()
