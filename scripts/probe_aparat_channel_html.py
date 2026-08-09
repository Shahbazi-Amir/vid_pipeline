from __future__ import annotations

import html
import json
import re
import urllib.request
from pathlib import Path

URL = "https://www.aparat.com/fintelligence/videos"
OUT = Path("sources/asre_shirin/channel_probe.json")


def main() -> None:
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.7",
        },
    )
    result: dict[str, object] = {"url": URL}
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            payload = response.read()
            result["status"] = int(getattr(response, "status", 200))
            result["content_type"] = response.headers.get("Content-Type", "")
        text = payload.decode("utf-8", errors="replace")
        decoded = html.unescape(text).replace("\\u002F", "/").replace("\\/", "/")
        ids = []
        for pattern in (
            r"https?://(?:www\.)?aparat\.com/v/([A-Za-z0-9]+)",
            r"(?:href|url)[\"'=:\s]+(?:https?://(?:www\.)?aparat\.com)?/v/([A-Za-z0-9]+)",
            r"/v/([A-Za-z0-9]{4,})",
        ):
            ids.extend(re.findall(pattern, decoded, flags=re.I))
        ids = list(dict.fromkeys(ids))
        result.update({
            "bytes": len(payload),
            "video_ids": ids,
            "video_id_count": len(ids),
            "contains_asre_shirin": "عصر شیرین" in decoded,
            "contains_financial_literacy": "سواد مالی" in decoded,
        })
        snippets = []
        for needle in ("عصر شیرین", "سواد مالی", "next", "cursor", "pagination", "fintelligence"):
            start = 0
            for _ in range(5):
                pos = decoded.casefold().find(needle.casefold(), start)
                if pos < 0:
                    break
                lo = max(0, pos - 250)
                hi = min(len(decoded), pos + 700)
                snippets.append({"needle": needle, "text": re.sub(r"\s+", " ", decoded[lo:hi])})
                start = pos + len(needle)
        result["snippets"] = snippets
    except Exception as exc:
        result.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in ("status", "bytes", "video_id_count", "contains_asre_shirin")}, ensure_ascii=False))
    if result.get("status") == "error":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
