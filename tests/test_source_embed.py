from __future__ import annotations

from unittest.mock import patch

from vid_pipeline.source import extract_page, normalize_video_url, webpage_candidate

HTML = b'''<html><head><title>Episode</title></head><body>
<script src="https://www.aparat.com/embed/G5HmM?data[rnddiv]=123&amp;data[responsive]=yes"></script>
</body></html>'''


def test_normalize_aparat_embed_url() -> None:
    assert normalize_video_url("https://www.aparat.com/embed/G5HmM?data[x]=1") == (
        "https://www.aparat.com/v/G5HmM"
    )


def test_extract_aparat_script_embed() -> None:
    with patch("vid_pipeline.source.fetch_bytes", return_value=(HTML, "text/html")):
        title, links, _ = extract_page("https://example.com/article")
        candidate = webpage_candidate("https://example.com/article")
    assert title == "Episode"
    assert "https://www.aparat.com/v/G5HmM" in links
    assert candidate.video_urls == ["https://www.aparat.com/v/G5HmM"]
