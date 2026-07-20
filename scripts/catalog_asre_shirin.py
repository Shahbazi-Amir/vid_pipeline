#!/usr/bin/env python3
"""Build a verified catalog of Asre Shirin season two from official sources."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

SITE = "https://www.fintelligence.ir/"
TELEGRAM = "https://t.me/s/fintelligence_ir"
USER_AGENT = "FinancialVideoRAGPipeline/1.1 (+https://github.com/Shahbazi-Amir/vid_pipeline)"

KNOWN_SEASON_ONE = {
    "6XCwb": "https://www.fintelligence.ir/Blog/Detail/B094D69C/x",
    "2ptDl": "https://www.fintelligence.ir/Blog/Detail/662BDA7F/x",
    "O51vh": "https://www.fintelligence.ir/Blog/Detail/5299D1D9/x",
    "ZSr7T": "https://www.fintelligence.ir/Blog/Detail/A97B7632/x",
    "lhE6W": "https://www.fintelligence.ir/Blog/Detail/3E26E509/x",
    "60uwC": "https://www.fintelligence.ir/Blog/Detail/BC0342B6/x",
    "T1hZM": "https://www.fintelligence.ir/Blog/Detail/BFAC7A6B/x",
    "xk2LT": "https://www.fintelligence.ir/Blog/Detail/7C8818DA/x",
    "oDFTR": "https://www.fintelligence.ir/Blog/Detail/7AB68D23/x",
    "zQd39": "https://www.fintelligence.ir/Blog/Detail/FD0665AE/x",
    "rbMBW": "https://www.fintelligence.ir/Blog/Detail/B7936C0D/x",
    "LrmDd": "https://www.fintelligence.ir/Blog/Detail/D15AE683/x",
    "G5HmM": "https://www.fintelligence.ir/Blog/Detail/A8A4080F/x",
}


@dataclass(slots=True)
class CatalogEntry:
    source_url: str
    video_url: str
    video_id: str
    title: str
    published_at: str
    sitemap_lastmod: str
    telegram_message_id: int | None
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


def request(url: str, timeout: int = 45) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", ""), response.geturl()


def extract_links(raw: str, base_url: str) -> list[str]:
    values = re.findall(r"(?:href|src)=[\"']([^\"']+)", raw, flags=re.I)
    values.extend(re.findall(r"https?://[^\s\"'<>]+", html.unescape(raw), flags=re.I))
    links: list[str] = []
    for value in values:
        value = html.unescape(value.strip())
        if not value or value.startswith(("javascript:", "mailto:", "tel:")):
            continue
        if value.startswith("//"):
            value = "https:" + value
        absolute = urllib.parse.urljoin(base_url, value)
        if urllib.parse.urlparse(absolute).scheme in {"http", "https"}:
            links.append(absolute.rstrip(".,);]"))
    return list(dict.fromkeys(links))


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
    decoded = urllib.parse.unquote(html.unescape(raw)).replace("\\/", "/")
    ids = re.findall(
        r"https?://(?:www\.)?aparat\.com/(?:v/|video/video/embed/videohash/)([A-Za-z0-9_-]+)",
        decoded,
        flags=re.I,
    )
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
    try:
        return (0, datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat())
    except ValueError:
        return (0, value)


def is_official_detail(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower() in {"fintelligence.ir", "www.fintelligence.ir"} and "/blog/detail/" in parsed.path.lower()


def sitemap_seeds(site: str) -> list[str]:
    root = urllib.parse.urljoin(site, "/")
    seeds = [
        urllib.parse.urljoin(root, "sitemap.xml"),
        urllib.parse.urljoin(root, "sitemap_index.xml"),
        urllib.parse.urljoin(root, "sitemap-index.xml"),
    ]
    try:
        robots, _, _ = request(urllib.parse.urljoin(root, "robots.txt"))
        for line in robots.decode("utf-8", errors="replace").splitlines():
            if line.lower().startswith("sitemap:"):
                seeds.append(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return list(dict.fromkeys(seeds))


def read_sitemaps(site: str, debug: list[dict[str, object]]) -> list[tuple[str, str]]:
    queue = sitemap_seeds(site)
    visited: set[str] = set()
    pages: list[tuple[str, str]] = []
    while queue and len(visited) < 100:
        sitemap = queue.pop(0)
        if sitemap in visited:
            continue
        visited.add(sitemap)
        try:
            payload, content_type, final_url = request(sitemap, timeout=60)
            root = ET.fromstring(payload)
            debug.append({"url": sitemap, "final_url": final_url, "content_type": content_type, "status": "parsed"})
        except Exception as exc:
            debug.append({"url": sitemap, "status": "failed", "error": str(exc)})
            continue
        if root.tag.endswith("sitemapindex"):
            for node in root:
                loc = next((item.text for item in node if item.tag.endswith("loc")), None)
                if loc:
                    queue.append(loc.strip())
            continue
        for node in root:
            loc = next((item.text for item in node if item.tag.endswith("loc")), None)
            lastmod = next((item.text for item in node if item.tag.endswith("lastmod")), "")
            if loc:
                pages.append((loc.strip(), (lastmod or "").strip()))
    return list(dict.fromkeys(pages))


def crawl_blog(site: str, debug: list[dict[str, object]], max_pages: int = 150) -> set[str]:
    host = urllib.parse.urlparse(site).netloc.lower()
    queue = [
        urllib.parse.urljoin(site, "/"),
        urllib.parse.urljoin(site, "/Blog"),
        urllib.parse.urljoin(site, "/Blog/Index"),
        *KNOWN_SEASON_ONE.values(),
    ]
    visited: set[str] = set()
    details: set[str] = set()
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            payload, content_type, final_url = request(url)
            raw = payload.decode("utf-8", errors="replace")
            debug.append({"url": url, "final_url": final_url, "content_type": content_type, "status": "fetched"})
        except Exception as exc:
            debug.append({"url": url, "status": "failed", "error": str(exc)})
            continue
        for link in extract_links(raw, final_url):
            parsed = urllib.parse.urlparse(link)
            if parsed.netloc.lower() != host:
                continue
            clean = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))
            if is_official_detail(clean):
                details.add(clean)
            elif parsed.path.lower().startswith("/blog") and clean not in visited:
                queue.append(clean)
    return details


def resolve_official_links(links: Iterable[str]) -> list[str]:
    official: list[str] = []
    for link in links:
        parsed = urllib.parse.urlparse(link)
        if parsed.netloc.lower().endswith("t.me"):
            continue
        try:
            payload, _, final_url = request(link, timeout=30)
            raw = payload.decode("utf-8", errors="replace")
        except Exception:
            continue
        if is_official_detail(final_url):
            official.append(final_url)
        for nested in extract_links(raw, final_url):
            if is_official_detail(nested):
                official.append(nested)
    return list(dict.fromkeys(official))


def crawl_telegram(max_pages: int = 45) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    before: int | None = None
    seen_messages: set[int] = set()
    evidence: dict[str, dict[str, object]] = {}
    debug: list[dict[str, object]] = []
    for _ in range(max_pages):
        url = TELEGRAM if before is None else f"{TELEGRAM}?before={before}"
        try:
            payload, content_type, final_url = request(url, timeout=60)
            raw = payload.decode("utf-8", errors="replace")
            debug.append({"url": url, "final_url": final_url, "content_type": content_type, "status": "fetched"})
        except Exception as exc:
            debug.append({"url": url, "status": "failed", "error": str(exc)})
            break
        matches = list(re.finditer(r'data-post="fintelligence_ir/(\d+)"', raw))
        ids = [int(match.group(1)) for match in matches]
        new_ids = [item for item in ids if item not in seen_messages]
        if not new_ids:
            break
        for index, match in enumerate(matches):
            message_id = int(match.group(1))
            if message_id in seen_messages:
                continue
            seen_messages.add(message_id)
            end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
            chunk = raw[match.start():end]
            normalized = extract_visible_text(chunk)
            if not (
                "عصر شیرین" in normalized
                or ("سواد مالی" in normalized and ("خانم" in normalized or "زنان" in normalized))
            ):
                continue
            official_links = resolve_official_links(extract_links(chunk, url))
            for source_url in official_links:
                item = evidence.setdefault(source_url, {"message_ids": [], "text": ""})
                item["message_ids"].append(message_id)
                item["text"] = normalize_text(f"{item['text']} {normalized}")
        next_before = min(ids)
        if before is not None and next_before >= before:
            break
        before = next_before
        if before < 500:
            break
    return evidence, debug


def inspect_page(url: str, lastmod: str, telegram_info: dict[str, object] | None) -> list[CatalogEntry]:
    payload, content_type, final_url = request(url, timeout=60)
    if "html" not in content_type.lower() and b"<html" not in payload[:1000].lower():
        return []
    raw = payload.decode("utf-8", errors="replace")
    title = extract_title(raw)
    visible = extract_visible_text(raw)
    telegram_text = normalize_text(str((telegram_info or {}).get("text", "")))
    combined = normalize_text(f"{title} {visible} {telegram_text}")
    speaker_verified = "کمیل رودی" in combined
    program_verified = "عصر شیرین" in combined or (
        "سواد مالی" in combined and ("خانم" in combined or "زنان" in combined)
    )
    evidence: list[str] = []
    if "کمیل رودی" in normalize_text(f"{title} {visible}"):
        evidence.append("page_mentions_komeil_roodi")
    elif "کمیل رودی" in telegram_text:
        evidence.append("official_channel_mentions_komeil_roodi")
    if "عصر شیرین" in combined:
        evidence.append("series_asre_shirin")
    if "سواد مالی" in combined and ("خانم" in combined or "زنان" in combined):
        evidence.append("financial_literacy_women_series")
    message_ids = [int(item) for item in (telegram_info or {}).get("message_ids", [])]
    entries: list[CatalogEntry] = []
    for video_url in extract_aparat_urls(raw):
        video_id = video_url.rstrip("/").rsplit("/", 1)[-1]
        entries.append(
            CatalogEntry(
                source_url=final_url,
                video_url=video_url,
                video_id=video_id,
                title=title,
                published_at=extract_date(raw),
                sitemap_lastmod=lastmod,
                telegram_message_id=min(message_ids) if message_ids else None,
                speaker_verified=speaker_verified,
                program_verified=program_verified,
                evidence=evidence,
            )
        )
    return entries


def relevant_slug(url: str) -> bool:
    decoded = normalize_text(urllib.parse.unquote(url)).casefold()
    return any(token in decoded for token in ("سواد مالی", "خانم", "زنان", "عصر شیرین"))


def season_two_sort_key(entry: CatalogEntry) -> tuple[int, object, str]:
    if entry.telegram_message_id is not None:
        return (0, entry.telegram_message_id, entry.source_url)
    return (1, date_key(entry.published_at or entry.sitemap_lastmod), entry.source_url)


def validate_anchors(entries: list[CatalogEntry]) -> list[str]:
    errors: list[str] = []
    if len(entries) != 13:
        return errors
    title8 = normalize_text(entries[7].title)
    title9 = normalize_text(entries[8].title)
    if "شریک" not in title8 and "شرکای کسب" not in title8:
        errors.append(f"episode_21_anchor_mismatch: {entries[7].title}")
    if "سرمایه انسانی" not in title9 and "سرمایۀ انسانی" not in entries[8].title:
        errors.append(f"episode_22_anchor_mismatch: {entries[8].title}")
    return errors


def build_catalog(site: str) -> dict[str, object]:
    sitemap_debug: list[dict[str, object]] = []
    sitemap_entries = read_sitemaps(site, sitemap_debug)
    blog_debug: list[dict[str, object]] = []
    blog_details = crawl_blog(site, blog_debug)
    telegram_evidence, telegram_debug = crawl_telegram()

    lastmods = {url: lastmod for url, lastmod in sitemap_entries}
    candidate_urls = set(blog_details) | set(telegram_evidence)
    candidate_urls.update(url for url, _ in sitemap_entries if is_official_detail(url) and relevant_slug(url))
    candidate_urls.update(KNOWN_SEASON_ONE.values())

    inspected: list[CatalogEntry] = []
    errors: list[dict[str, str]] = []
    for url in sorted(candidate_urls):
        if url not in telegram_evidence and url not in KNOWN_SEASON_ONE.values() and not relevant_slug(url):
            continue
        try:
            inspected.extend(inspect_page(url, lastmods.get(url, ""), telegram_evidence.get(url)))
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})

    unique: dict[str, CatalogEntry] = {}
    for entry in inspected:
        existing = unique.get(entry.video_id)
        score = len(entry.evidence) + int(entry.telegram_message_id is not None)
        old_score = len(existing.evidence) + int(existing.telegram_message_id is not None) if existing else -1
        if existing is None or score > old_score:
            unique[entry.video_id] = entry

    official = [entry for entry in unique.values() if entry.speaker_verified and entry.program_verified]
    season_one = [entry for entry in official if entry.video_id in KNOWN_SEASON_ONE]
    season_two = [entry for entry in official if entry.video_id not in KNOWN_SEASON_ONE]
    season_two.sort(key=season_two_sort_key)
    if len(season_two) == 13:
        for index, entry in enumerate(season_two, 1):
            entry.season_episode = index
            entry.overall_episode = index + 13
    anchor_errors = validate_anchors(season_two)
    status = "ready" if len(season_two) == 13 and not anchor_errors else "needs_investigation"
    return {
        "schema_version": 2,
        "site": site,
        "status": status,
        "sitemap_urls": len(sitemap_entries),
        "blog_detail_urls": len(blog_details),
        "telegram_official_urls": len(telegram_evidence),
        "candidate_urls": len(candidate_urls),
        "official_unique_videos": len(official),
        "season_one_matches": len(season_one),
        "season_two_matches": len(season_two),
        "anchor_errors": anchor_errors,
        "season_two": [entry.to_dict() for entry in season_two],
        "unclassified": [entry.to_dict() for entry in unique.values() if entry not in official],
        "errors": errors,
        "debug": {"sitemaps": sitemap_debug, "blog": blog_debug, "telegram": telegram_debug},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--output", type=Path, default=Path("data/asre-shirin-season-2-catalog.json"))
    args = parser.parse_args()
    result = build_catalog(args.site)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_keys = (
        "status",
        "sitemap_urls",
        "blog_detail_urls",
        "telegram_official_urls",
        "candidate_urls",
        "season_one_matches",
        "season_two_matches",
        "anchor_errors",
    )
    print(json.dumps({key: result[key] for key in summary_keys}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
