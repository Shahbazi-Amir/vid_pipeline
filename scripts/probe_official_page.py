#!/usr/bin/env python3
"""Capture video-related HTML evidence from one official article page."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "FinancialVideoRAGPipeline/1.2 (+https://github.com/Shahbazi-Amir/vid_pipeline)"
KEYWORDS = (
    "aparat",
    "videohash",
    "videoHash",
    "iframe",
    "embed",
    "player",
    "video",
    "G5HmM",
    "A8A4080F",
)


def fetch(url: str) -> tuple[str, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return payload, response.geturl(), response.headers.get("Content-Type", "")


def snippets(raw: str, keyword: str, radius: int = 350) -> list[str]:
    results: list[str] = []
    for match in re.finditer(re.escape(keyword), raw, flags=re.I):
        start = max(0, match.start() - radius)
        end = min(len(raw), match.end() + radius)
        value = raw[start:end]
        value = value.replace("\r", " ").replace("\n", " ")
        value = re.sub(r"\s+", " ", value)
        results.append(value)
        if len(results) >= 20:
            break
    return results


def attributes(raw: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for attribute in ("src", "href", "data-src", "data-video", "data-hash", "content"):
        values = re.findall(
            rf"{attribute}\s*=\s*[\"']([^\"']+)",
            raw,
            flags=re.I,
        )
        decoded = [html.unescape(urllib.parse.unquote(item.replace("\\/", "/"))) for item in values]
        result[attribute] = list(dict.fromkeys(decoded))
    return result


def candidate_tokens(raw: str) -> list[str]:
    decoded = html.unescape(urllib.parse.unquote(raw.replace("\\/", "/")))
    patterns = (
        r"https?://[^\s\"'<>]+",
        r"(?:videohash|videoHash|video_id|videoId|aparatId|aparat_id)\s*[:=]\s*[\"']?([A-Za-z0-9_-]{4,})",
        r"(?:/v/|videohash/)([A-Za-z0-9_-]{4,})",
    )
    values: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, decoded, flags=re.I):
            value = match if isinstance(match, str) else "".join(match)
            if any(term.lower() in value.lower() for term in ("aparat", "video", "embed", "G5HmM")) or re.fullmatch(r"[A-Za-z0-9_-]{4,}", value):
                values.append(value.rstrip(".,);]"))
    return list(dict.fromkeys(values))[:500]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.fintelligence.ir/Blog/Detail/A8A4080F/x")
    parser.add_argument("--output", type=Path, default=Path("data/official-page-probe.json"))
    args = parser.parse_args()

    raw, final_url, content_type = fetch(args.url)
    attrs = attributes(raw)
    relevant_attrs = {
        key: [
            value
            for value in values
            if any(term.lower() in value.lower() for term in ("aparat", "video", "embed", "player", "G5HmM"))
        ]
        for key, values in attrs.items()
    }
    result = {
        "requested_url": args.url,
        "final_url": final_url,
        "content_type": content_type,
        "html_length": len(raw),
        "keyword_counts": {keyword: len(re.findall(re.escape(keyword), raw, flags=re.I)) for keyword in KEYWORDS},
        "snippets": {keyword: snippets(raw, keyword) for keyword in KEYWORDS},
        "relevant_attributes": relevant_attrs,
        "candidate_tokens": candidate_tokens(raw),
        "script_src": attrs.get("src", []),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"html_length": len(raw), "keyword_counts": result["keyword_counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
