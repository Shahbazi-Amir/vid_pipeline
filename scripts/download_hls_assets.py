#!/usr/bin/env python3
"""Download an HLS VOD playlist and its assets through curl for local FFmpeg use."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

_STREAM_RE = re.compile(r"^#EXT-X-STREAM-INF:(?P<attrs>.+)$")
_URI_ATTR_RE = re.compile(r'URI="(?P<uri>[^"]+)"')
_BANDWIDTH_RE = re.compile(r"(?:^|,)BANDWIDTH=(?P<value>\d+)(?:,|$)")
_RESOLUTION_RE = re.compile(r"(?:^|,)RESOLUTION=(?P<width>\d+)x(?P<height>\d+)(?:,|$)")


@dataclass(frozen=True, slots=True)
class Variant:
    uri: str
    bandwidth: int
    width: int
    height: int


def run_curl(curl: str, url: str, output: Path, *, timeout: int = 900) -> str:
    """Download one URL atomically and return curl's effective URL."""

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    command = [
        curl,
        "-4",
        "--silent",
        "--show-error",
        "--fail",
        "--location",
        "--retry",
        "10",
        "--retry-all-errors",
        "--retry-delay",
        "3",
        "--connect-timeout",
        "30",
        "--max-time",
        str(timeout),
        "-A",
        "Mozilla/5.0",
        "--write-out",
        "%{url_effective}",
        "--output",
        str(temporary),
        url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        message = result.stderr.strip() or result.stdout.strip() or "unknown curl error"
        raise RuntimeError(f"curl failed for {url}: {message}")
    if not temporary.exists() or temporary.stat().st_size == 0:
        raise RuntimeError(f"curl created an empty file for {url}")
    temporary.replace(output)
    return result.stdout.strip() or url


def parse_variants(text: str) -> list[Variant]:
    """Parse HLS master variants while preserving their declared media URI."""

    lines = [line.strip() for line in text.splitlines()]
    variants: list[Variant] = []
    for index, line in enumerate(lines):
        match = _STREAM_RE.match(line)
        if not match:
            continue
        uri = next(
            (
                candidate
                for candidate in lines[index + 1 :]
                if candidate and not candidate.startswith("#")
            ),
            "",
        )
        if not uri:
            continue
        attrs = match.group("attrs")
        bandwidth_match = _BANDWIDTH_RE.search(attrs)
        resolution_match = _RESOLUTION_RE.search(attrs)
        variants.append(
            Variant(
                uri=uri,
                bandwidth=int(bandwidth_match.group("value")) if bandwidth_match else 0,
                width=int(resolution_match.group("width")) if resolution_match else 0,
                height=int(resolution_match.group("height")) if resolution_match else 0,
            )
        )
    return variants


def select_smallest_variant(variants: Iterable[Variant]) -> Variant:
    """Choose the lowest-bandwidth usable variant to minimize transfer size."""

    values = list(variants)
    if not values:
        raise ValueError("The master playlist does not contain a media variant.")
    return min(values, key=lambda item: (item.bandwidth or sys.maxsize, item.height, item.width))


def playlist_references(text: str) -> list[str]:
    """Return unique media, initialization, and key references in playlist order."""

    references: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        candidates: list[str] = []
        if line and not line.startswith("#"):
            candidates.append(line)
        candidates.extend(match.group("uri") for match in _URI_ATTR_RE.finditer(line))
        for candidate in candidates:
            if candidate not in seen:
                references.append(candidate)
                seen.add(candidate)
    return references


def asset_filename(index: int, reference: str) -> str:
    """Create a stable local filename while retaining a useful media suffix."""

    suffix = Path(urlparse(reference).path).suffix
    if not suffix or len(suffix) > 12:
        suffix = ".bin"
    return f"asset-{index:05d}{suffix}"


def rewrite_playlist(text: str, mapping: dict[str, str]) -> str:
    """Rewrite all external references to local forward-slash paths."""

    output: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped in mapping and stripped and not stripped.startswith("#"):
            output.append(mapping[stripped])
            continue

        def replace_uri(match: re.Match[str]) -> str:
            uri = match.group("uri")
            return f'URI="{mapping.get(uri, uri)}"'

        output.append(_URI_ATTR_RE.sub(replace_uri, raw_line))
    return "\n".join(output).rstrip() + "\n"


def download_hls(master_url: str, output_dir: Path, *, workers: int = 8) -> dict[str, object]:
    """Download a master playlist, its smallest VOD variant, and all referenced assets."""

    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("curl was not found in PATH")
    if workers < 1:
        raise ValueError("workers must be at least 1")

    output_dir.mkdir(parents=True, exist_ok=True)
    master_path = output_dir / "master.m3u8"
    effective_master = run_curl(curl, master_url, master_path, timeout=240)
    master_text = master_path.read_text(encoding="utf-8-sig")
    variant = select_smallest_variant(parse_variants(master_text))
    variant_url = urljoin(effective_master, variant.uri)

    remote_variant_path = output_dir / "variant.remote.m3u8"
    effective_variant = run_curl(curl, variant_url, remote_variant_path, timeout=240)
    variant_text = remote_variant_path.read_text(encoding="utf-8-sig")
    references = playlist_references(variant_text)
    if not references:
        raise RuntimeError("The media playlist does not contain downloadable assets.")

    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        reference: f"media/{asset_filename(index, reference)}"
        for index, reference in enumerate(references)
    }

    def download_one(item: tuple[str, str]) -> tuple[str, int]:
        reference, relative_path = item
        source_url = urljoin(effective_variant, reference)
        destination = output_dir / Path(relative_path)
        run_curl(curl, source_url, destination)
        return relative_path, destination.stat().st_size

    total_bytes = 0
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_one, item): item[0]
            for item in mapping.items()
        }
        for future in concurrent.futures.as_completed(futures):
            _, size = future.result()
            total_bytes += size
            completed += 1
            if completed == 1 or completed % 25 == 0 or completed == len(futures):
                print(f"Downloaded {completed}/{len(futures)} HLS assets", flush=True)

    local_playlist = output_dir / "playlist.local.m3u8"
    local_playlist.write_text(rewrite_playlist(variant_text, mapping), encoding="utf-8")
    metadata = {
        "master_url": master_url,
        "effective_master_url": effective_master,
        "variant_url": variant_url,
        "effective_variant_url": effective_variant,
        "selected_variant": {
            "bandwidth": variant.bandwidth,
            "width": variant.width,
            "height": variant.height,
        },
        "asset_count": len(references),
        "total_bytes": total_bytes,
        "local_playlist": str(local_playlist),
    }
    (output_dir / "download.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master_url")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    metadata = download_hls(args.master_url, args.output_dir, workers=args.workers)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
