"""Source discovery and validation without a paid search API."""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from vid_pipeline.errors import PipelineError

USER_AGENT = "FinancialVideoRAGPipeline/1.0 (+https://github.com/Shahbazi-Amir/vid_pipeline)"
VIDEO_HOSTS = {"aparat.com", "www.aparat.com", "youtube.com", "www.youtube.com", "youtu.be"}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._inside_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag in {"iframe", "video", "source"} and values.get("src"):
            self.links.append(values["src"] or "")
        if tag == "title":
            self._inside_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self.title_parts.append(data)


@dataclass(slots=True)
class SourceCandidate:
    page_url: str
    title: str
    video_urls: list[str]
    score: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def fetch_bytes(url: str, timeout: int = 30) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            return response.read(), content_type
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PipelineError(f"Could not fetch {url}: {exc}") from exc


def normalize_url(base_url: str, value: str) -> str:
    value = html.unescape(value.strip())
    if value.startswith("//"):
        value = "https:" + value
    return urllib.parse.urljoin(base_url, value)


def is_http_url(value: str) -> bool:
    return urllib.parse.urlparse(value).scheme in {"http", "https"}


def is_video_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host in VIDEO_HOSTS or any(host.endswith("." + item) for item in VIDEO_HOSTS)


def extract_page(url: str) -> tuple[str, list[str], str]:
    payload, content_type = fetch_bytes(url)
    if "html" not in content_type and not url.lower().endswith((".html", "/")):
        raise PipelineError(f"Expected an HTML page, got {content_type or 'unknown content type'}.")
    text = payload.decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(text)
    links = [normalize_url(url, item) for item in parser.links if item]
    embedded_patterns = (
        r"https?://(?:www\.)?aparat\.com/v/[A-Za-z0-9_-]+",
        r"https?://youtu\.be/[A-Za-z0-9_-]+",
        r"https?://(?:www\.)?youtube\.com/(?:watch\?v=|embed/)[A-Za-z0-9_-]+",
    )
    for pattern in embedded_patterns:
        links.extend(html.unescape(item) for item in re.findall(pattern, text, flags=re.I))
    links = list(dict.fromkeys(links))
    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
    visible_text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    visible_text = re.sub(r"<style\b[^>]*>.*?</style>", " ", visible_text, flags=re.I | re.S)
    visible_text = re.sub(r"<[^>]+>", " ", visible_text)
    visible_text = re.sub(r"\s+", " ", html.unescape(visible_text))
    return title, links, visible_text


def webpage_candidate(url: str, query: str = "") -> SourceCandidate:
    title, links, text = extract_page(url)
    video_urls = list(dict.fromkeys(link for link in links if is_video_url(link)))
    tokens = [token for token in re.split(r"\s+", query.strip()) if len(token) > 1]
    haystack = f"{title} {url} {text[:10000]}".casefold()
    score = sum(
        3 if token.casefold() in title.casefold() else 1
        for token in tokens
        if token.casefold() in haystack
    )
    return SourceCandidate(page_url=url, title=title, video_urls=video_urls, score=score)


def sitemap_urls(site_url: str, limit: int = 5000) -> list[str]:
    parsed = urllib.parse.urlparse(site_url)
    first = urllib.parse.urlunparse(
        (parsed.scheme or "https", parsed.netloc, "/sitemap.xml", "", "", "")
    )
    queue = [first]
    visited: set[str] = set()
    pages: list[str] = []
    while queue and len(pages) < limit:
        sitemap = queue.pop(0)
        if sitemap in visited:
            continue
        visited.add(sitemap)
        try:
            payload, _ = fetch_bytes(sitemap)
            root = ET.fromstring(payload)
        except (PipelineError, ET.ParseError):
            continue
        locations = [
            element.text.strip()
            for element in root.iter()
            if element.tag.endswith("loc")
            and element.text
            and is_http_url(element.text.strip())
        ]
        if root.tag.endswith("sitemapindex"):
            queue.extend(location for location in locations if location not in visited)
        else:
            pages.extend(locations[: max(0, limit - len(pages))])
    return list(dict.fromkeys(pages))


def _url_score(url: str, tokens: Iterable[str]) -> int:
    decoded = urllib.parse.unquote(url).casefold()
    return sum(1 for token in tokens if token.casefold() in decoded)


def discover_site(site_url: str, query: str, max_pages: int = 30) -> list[SourceCandidate]:
    """Search a site's sitemap, then inspect the best matching pages."""
    tokens = [token for token in re.split(r"\s+", query.strip()) if len(token) > 1]
    urls = sitemap_urls(site_url)
    ranked = sorted(urls, key=lambda item: _url_score(item, tokens), reverse=True)
    candidates: list[SourceCandidate] = []
    inspected = 0
    for url in ranked:
        if inspected >= max_pages:
            break
        if tokens and _url_score(url, tokens) == 0 and inspected >= min(5, max_pages):
            continue
        inspected += 1
        try:
            candidate = webpage_candidate(url, query)
        except PipelineError:
            continue
        if candidate.score or candidate.video_urls:
            candidates.append(candidate)
    candidates.sort(key=lambda item: (bool(item.video_urls), item.score), reverse=True)
    return candidates


def validate_source(input_value: str, query: str = "") -> SourceCandidate:
    if not is_http_url(input_value):
        raise PipelineError("Source validation requires an http or https URL.")
    if is_video_url(input_value):
        return SourceCandidate(page_url=input_value, title="", video_urls=[input_value], score=0)
    return webpage_candidate(input_value, query)


def save_candidates(candidates: list[SourceCandidate], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps([item.to_dict() for item in candidates], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
