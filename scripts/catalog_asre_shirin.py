#!/usr/bin/env python3
"""Build a verified catalog of Asre Shirin season two from the official site."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from vid_pipeline.source import fetch_bytes, is_http_url

SITE = "https://www.fintelligence.ir/"
KNOWN_SEASON_ONE_VIDEO_IDS = {
    "6XCwb",
    "2ptDl",
    "O51vh",
    "ZSr7T",
    "lhE6W",
    "60uwC",
    "T1hZM",
    "xk2LT",
    "oDFTR",
    "zQd39",
    "rbMBW",
    "LrmDd",
    "G5HmM",
}


@dataclass(slots=True)
class CatalogEntry:
    source_url: str
    video_url: str
    video_id: str
    title: str
    published_at: str
    sitemap_lastmod: str
    speaker_verified: bool
    program_verified: bool
    evidence: list[str]
    overall_episode: int | None = None
    season_episode: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_text(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = value.replace("ۀ", "ه").replace("ة", "ه")
    return re.sub(r"\s+", " ", value).strip()


def sitemap_seeds(site: str) -> list[str]:
    parsed = urllib.parse.urlparse(site)
    root = urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc, "/", "", "", ""))
    seeds = [
        urllib.parse.urljoin(root, "sitemap.xml"),
        urllib.parse.urljoin(root, "sitemap_index.xml"),
        urllib.parse.urljoin(root, "sitemap-index.xml"),
    ]
    try:
        robots, _ = fetch_bytes(urllib.parse.urljoin(root, "robots.txt"))
        for line in robots.decode("utf-8", errors="replace").splitlines():
            if line.lower().startswith("sitemap:"):
                value = line.split(":", 1)[1].strip()
                if is_http_url(value):
                    seeds.append(value)
    except Exception:
        pass
    return list(dict.fromkeys(seeds))


def read_sitemaps(site: str, limit: int = 50000) -> list[tuple[str, str]]:
    queue = sitemap_seeds(site)
    visited: set[str] = set()
    pages: list[tuple[str, str]] = []
    while queue and len(pages) < limit:
        sitemap = queue.pop(0)
        if sitemap in visited:
            continue
        visited.add(sitemap)
        try:
            payload, _ = fetch_bytes(sitemap, timeout=60)
            root = ET.fromstring(payload)
        except Exception:
            continue
        if root.tag.endswith("sitemapindex"):
            for node in root:
                loc = next((item.text for item in node if item.tag.endswith("loc")), None)
                if loc and is_http_url(loc.strip()):
                    queue.append(loc.strip())
            continue
        for node in root:
            loc = next((item.text for item in node if item.tag.endswith("loc")), None)
            lastmod = next((item.text for item in node if item.tag.endswith("lastmod")), "")
            if loc and is_http_url(loc.strip()):
                pages.append((loc.strip(), (lastmod or "").strip()))
    deduped: dict[str, str] = {}
    for url, lastmod in pages:
        deduped[url] = lastmod or deduped.get(url, "")
    return list(deduped.items())


def extract_title(raw: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title[^>]*>(.*?)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I | re.S)
        if match:
            return normalize_text(re.sub(r"<[^>]+>", " ", match.group(1)))
    return ""


def extract_visible_text(raw: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return normalize_text(value)


def extract_aparat_urls(raw: str) -> list[str]:
    patterns = [
        r"https?://(?:www\.)?aparat\.com/v/([A-Za-z0-9_-]+)",
        r"https?%3A%2F%2F(?:www\.)?aparat\.com%2Fv%2F([A-Za-z0-9_-]+)",
    ]
    ids: list[str] = []
    decoded = urllib.parse.unquote(html.unescape(raw))
    for pattern in patterns:
        ids.extend(re.findall(pattern, decoded, flags=re.I))
    return [f"https://www.aparat.com/v/{item}" for item in dict.fromkeys(ids)]


def extract_date(raw: str) -> str:
    patterns = [
        r'["\']datePublished["\']\s*:\s*["\']([^"\']+)',
        r'property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
        r'content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
        r'["\']uploadDate["\']\s*:\s*["\']([^"\']+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            return match.group(1).strip()
    return ""


def date_key(value: str) -> tuple[int, str]:
    if not value:
        return (1, "")
    candidate = value.replace("Z", "+00:00")
    try:
        return (0, datetime.fromisoformat(candidate).isoformat())
    except ValueError:
        return (0, value)


def looks_relevant_url(url: str) -> bool:
    decoded = normalize_text(urllib.parse.unquote(url)).casefold()
    if "/blog/detail/" not in decoded:
        return False
    signals = ("سواد مالی", "خانم", "زنان", "عصر شیرین")
    return any(item.casefold() in decoded for item in signals)


def inspect_page(url: str, lastmod: str) -> list[CatalogEntry]:
    payload, content_type = fetch_bytes(url, timeout=60)
    if "html" not in content_type.lower() and b"<html" not in payload[:1000].lower():
        return []
    raw = payload.decode("utf-8", errors="replace")
    title = extract_title(raw)
    visible = extract_visible_text(raw)
    combined = normalize_text(f"{title} {visible}")
    speaker_verified = "کمیل رودی" in combined
    program_verified = "عصر شیرین" in combined or (
        "سواد مالی" in combined and ("خانم" in combined or "زنان" in combined)
    )
    evidence: list[str] = []
    if speaker_verified:
        evidence.append("page_mentions_komeil_roodi")
    if "عصر شیرین" in combined:
        evidence.append("page_mentions_asre_shirin")
    if "سواد مالی" in combined and ("خانم" in combined or "زنان" in combined):
        evidence.append("page_matches_financial_literacy_women_series")
    entries: list[CatalogEntry] = []
    for video_url in extract_aparat_urls(raw):
        video_id = video_url.rstrip("/").rsplit("/", 1)[-1]
        entries.append(
            CatalogEntry(
                source_url=url,
                video_url=video_url,
                video_id=video_id,
                title=title,
                published_at=extract_date(raw),
                sitemap_lastmod=lastmod,
                speaker_verified=speaker_verified,
                program_verified=program_verified,
                evidence=evidence,
            )
        )
    return entries


def build_catalog(site: str) -> dict[str, object]:
    sitemap_entries = read_sitemaps(site)
    likely = [item for item in sitemap_entries if looks_relevant_url(item[0])]
    inspected: list[CatalogEntry] = []
    errors: list[dict[str, str]] = []
    for url, lastmod in likely:
        try:
            inspected.extend(inspect_page(url, lastmod))
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})
    unique: dict[str, CatalogEntry] = {}
    for entry in inspected:
        existing = unique.get(entry.video_id)
        if existing is None or len(entry.evidence) > len(existing.evidence):
            unique[entry.video_id] = entry
    official = [
        entry
        for entry in unique.values()
        if entry.speaker_verified and entry.program_verified
    ]
    season_one = [entry for entry in official if entry.video_id in KNOWN_SEASON_ONE_VIDEO_IDS]
    season_two = [entry for entry in official if entry.video_id not in KNOWN_SEASON_ONE_VIDEO_IDS]
    season_two.sort(key=lambda item: date_key(item.published_at or item.sitemap_lastmod))
    if len(season_two) == 13:
        for index, entry in enumerate(season_two, 1):
            entry.season_episode = index
            entry.overall_episode = index + 13
    status = "ready" if len(season_one) == 13 and len(season_two) == 13 else "needs_investigation"
    return {
        "schema_version": 1,
        "site": site,
        "status": status,
        "sitemap_urls": len(sitemap_entries),
        "likely_pages": len(likely),
        "official_unique_videos": len(official),
        "season_one_matches": len(season_one),
        "season_two_matches": len(season_two),
        "season_two": [entry.to_dict() for entry in season_two],
        "unclassified": [
            entry.to_dict()
            for entry in unique.values()
            if entry not in official
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--output", type=Path, default=Path("data/asre-shirin-season-2-catalog.json"))
    args = parser.parse_args()
    result = build_catalog(args.site)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "sitemap_urls", "likely_pages", "season_one_matches", "season_two_matches")}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
