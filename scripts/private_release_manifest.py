from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

API = "https://api.github.com"
MEDIA_SUFFIXES = {
    ".mp4",
    ".mkv",
    ".mov",
    ".webm",
    ".m4v",
    ".avi",
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
}


def api_json(path: str):
    token = os.environ["PRIVATE_MEDIA_TOKEN"].strip()
    request = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "vid-pipeline-private-release-manifest",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def normalize(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", value.strip().casefold())


def natural_key(value: str):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def leading_number(name: str) -> int | None:
    match = re.match(r"^(\d+)(?:[. _-]|$)", Path(name).name)
    return int(match.group(1)) if match else None


def choose_release(releases: list[dict], selector: str) -> dict:
    published = [item for item in releases if not item.get("draft")]
    wanted = normalize(selector)
    exact = [
        item
        for item in published
        if wanted
        in {
            normalize(str(item.get("name") or "")),
            normalize(str(item.get("tag_name") or "")),
        }
    ]
    if len(exact) == 1:
        return exact[0]
    fuzzy = [
        item
        for item in published
        if wanted
        and (
            wanted in normalize(str(item.get("name") or ""))
            or wanted in normalize(str(item.get("tag_name") or ""))
        )
    ]
    if len(fuzzy) == 1:
        return fuzzy[0]
    if not exact and not fuzzy:
        raise SystemExit("Requested published private release was not found")
    raise SystemExit("Private release selector is ambiguous")


def main() -> None:
    repo = os.environ["PRIVATE_MEDIA_REPO"].strip()
    selector = os.environ["RELEASE_SELECTOR"].strip()
    mode = os.environ.get("NUMBERING_MODE", "auto").strip().casefold()
    expected_raw = os.environ.get("EXPECTED_NUMBERS", "").strip()

    releases = api_json(f"/repos/{repo}/releases?per_page=100")
    release = choose_release(releases, selector)
    release_id = int(release["id"])
    assets = api_json(f"/repos/{repo}/releases/{release_id}/assets?per_page=100")
    assets = [
        item
        for item in assets
        if item.get("state") == "uploaded"
        and Path(str(item.get("name") or "")).suffix.casefold() in MEDIA_SUFFIXES
    ]
    assets.sort(key=lambda item: natural_key(str(item.get("name") or "")))
    if not assets:
        raise SystemExit("Selected private release has no supported uploaded media assets")

    inferred = [leading_number(str(item["name"])) for item in assets]
    if mode == "leading":
        if any(number is None for number in inferred):
            raise SystemExit("A release asset is missing the required leading result number")
        numbers = [int(number) for number in inferred]
    elif mode == "auto" and all(number is not None for number in inferred) and len(set(inferred)) == len(inferred):
        numbers = [int(number) for number in inferred]
    elif mode == "auto":
        numbers = list(range(1, len(assets) + 1))
    else:
        raise SystemExit("Unsupported numbering mode")

    if len(set(numbers)) != len(numbers):
        raise SystemExit("Duplicate result numbers were inferred from private release assets")

    if expected_raw:
        expected = {int(item.strip()) for item in expected_raw.split(",") if item.strip()}
        actual = set(numbers)
        if actual != expected:
            raise SystemExit("Selected private release does not contain the expected result-number set")

    include = []
    for asset, number in zip(assets, numbers, strict=True):
        include.append(
            {
                "asset_id": int(asset["id"]),
                "size": int(asset["size"]),
                "digest": str(asset.get("digest") or ""),
                "suffix": Path(str(asset["name"])).suffix.casefold(),
                "result_number": number,
            }
        )

    matrix = json.dumps({"include": include}, separators=(",", ":"), ensure_ascii=False)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
        handle.write(f"matrix={matrix}\n")
        handle.write(f"count={len(include)}\n")
    print(f"Discovered {len(include)} private media assets")


if __name__ == "__main__":
    main()
