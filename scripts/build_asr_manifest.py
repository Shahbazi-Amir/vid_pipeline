"""Build the immutable ASR release manifest from a real packaged CT2 model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()

    tag = "asr-model-large-v3-turbo-ct2-v1"
    files = []
    for path in sorted(candidate for candidate in args.model_dir.rglob("*") if candidate.is_file()):
        files.append(
            {
                "path": path.relative_to(args.model_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    required = {"model.bin", "config.json", "tokenizer.json", "preprocessor_config.json"}
    missing = required - {item["path"] for item in files}
    if missing:
        raise SystemExit(f"CT2 model is incomplete; missing {sorted(missing)}")

    manifest = {
        "schema_version": 1,
        "name": "large-v3-turbo",
        "format": "CTranslate2",
        "artifact_version": "large-v3-turbo-ct2-v1",
        "release_tag": tag,
        "asset_name": args.archive.name,
        "asset_url": (
            f"https://github.com/{args.repository}/releases/download/{tag}/{args.archive.name}"
        ),
        "asset_size": args.archive.stat().st_size,
        "asset_sha256": digest(args.archive),
        "files": files,
        "source_provenance": {
            "repository": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
            "revision": args.source_revision,
            "base_model": "openai/whisper-large-v3-turbo",
            "conversion": (
                "ct2-transformers-converter with tokenizer.json and "
                "preprocessor_config.json copied; FP16 weights"
            ),
        },
        "license": "MIT",
        "faster_whisper_version": "1.2.1",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
