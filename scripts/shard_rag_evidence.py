"""Download the approved public evidence release and create lossless JSONL shards."""
import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

URL = "https://github.com/Shahbazi-Amir/vid_pipeline/releases/download/rag_finance/context_evidence_registry_v1.jsonl"
EXPECTED_SHA = "730aad40c0dac5c94d702f0a22aa3a891045f458a445abd087f34303bebe9fe2"
EXPECTED_BYTES = 74972073
LIMIT = 5 * 1024 * 1024
OUTPUT = Path("experiments/rag20/evidence_shards")


def check(ok, message):
    if not ok:
        raise ValueError(message)


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def split(source, destination, limit=LIMIT):
    destination.mkdir(parents=True, exist_ok=False)
    parts, index, combined = [], {}, hashlib.sha256()
    handle = None
    part_bytes = 0
    try:
        with source.open("rb") as incoming:
            for line in incoming:
                check(line.strip(), "Blank JSONL record")
                check(len(line) <= limit, "One record exceeds the shard limit")
                row = json.loads(line.decode("utf-8"))
                evidence_id = row["evidence_id"]
                check(isinstance(evidence_id, str) and evidence_id, "Invalid evidence ID")
                check(evidence_id not in index, "Duplicate evidence ID")
                if handle is None or part_bytes + len(line) > limit:
                    if handle is not None:
                        handle.close()
                    name = f"part-{len(parts) + 1:03d}.jsonl"
                    parts.append(name)
                    handle = (destination / name).open("wb")
                    part_bytes = 0
                handle.write(line)
                part_bytes += len(line)
                combined.update(line)
                index[evidence_id] = parts[-1]
    finally:
        if handle is not None:
            handle.close()
    check(parts, "Empty input")
    check(combined.hexdigest() == file_sha(source), "Split changed source bytes")
    reread = hashlib.sha256()
    for name in parts:
        with (destination / name).open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                reread.update(block)
    check(reread.hexdigest() == file_sha(source), "Independent concatenation mismatch")
    result = {
        "schema_version": "rag_evidence_shards_v1",
        "source_sha256": file_sha(source),
        "source_bytes": source.stat().st_size,
        "record_count": len(index),
        "shard_limit_bytes": limit,
        "lossless_reassembly_verified": True,
        "parts": [{"path": name, "bytes": (destination / name).stat().st_size,
                   "sha256": file_sha(destination / name)} for name in parts],
        "evidence_id_to_part": index,
    }
    (destination / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def self_test():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / "input.jsonl"
        lines = [json.dumps({"evidence_id": str(i), "content": "شاهد"},
                           ensure_ascii=False).encode("utf-8") + b"\n" for i in range(4)]
        source.write_bytes(b"".join(lines))
        result = split(source, root / "valid", len(lines[0]) * 2)
        check(len(result["parts"]) == 2, "Boundary test failed")
        check(b"".join((root / "valid" / p["path"]).read_bytes()
                      for p in result["parts"]) == source.read_bytes(), "Byte preservation failed")
        source.write_bytes(lines[0] + lines[0])
        try:
            split(source, root / "duplicate")
        except ValueError:
            pass
        else:
            raise ValueError("Duplicate was accepted")
        source.write_bytes(b"{bad json}\n")
        try:
            split(source, root / "malformed")
        except (ValueError, KeyError):
            pass
        else:
            raise ValueError("Malformed JSON was accepted")
        source.write_bytes(lines[0])
        try:
            split(source, root / "oversize", len(lines[0]) - 1)
        except ValueError:
            pass
        else:
            raise ValueError("Oversize record was accepted")
    print("SELF_TEST_PASS")


def run():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / "registry.jsonl"
        count = 0
        request = urllib.request.Request(URL, headers={"User-Agent": "vid-pipeline-evidence-sharder"})
        with urllib.request.urlopen(request, timeout=60) as response, source.open("wb") as handle:
            for block in iter(lambda: response.read(65536), b""):
                count += len(block)
                check(count <= EXPECTED_BYTES, "Download larger than the frozen source")
                handle.write(block)
        check(count == EXPECTED_BYTES, "Source length mismatch")
        check(file_sha(source) == EXPECTED_SHA, "Frozen NB19 evidence hash mismatch")
        generated = root / "shards"
        manifest = split(source, generated)
        check(manifest["record_count"] == 3355, "Unexpected evidence count")
        if OUTPUT.exists():
            expected = sorted(p.name for p in generated.iterdir())
            check(sorted(p.name for p in OUTPUT.iterdir()) == expected, "Existing file set differs")
            for name in expected:
                check(file_sha(OUTPUT / name) == file_sha(generated / name),
                      "Existing output differs: " + name)
            status = "EXISTING_SHARDS_VERIFIED"
        else:
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            generated.replace(OUTPUT)
            status = "SHARDS_CREATED"
        print(json.dumps({"status": status, "shards": len(manifest["parts"]),
                          "records": manifest["record_count"], "source_sha256": EXPECTED_SHA,
                          "lossless_reassembly_verified": True}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        run()
