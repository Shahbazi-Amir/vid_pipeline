"""Import the exact original pilot ZIP from the user-provided repository release."""
import hashlib, json, urllib.request, zipfile, stat
from pathlib import Path, PurePosixPath
ROOT = Path("experiments/rag20/batches/test_001_020")
URL = "https://github.com/Shahbazi-Amir/vid_pipeline/releases/download/rag_finance/rag20_agent_pilot_v1.zip"
def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    raw = urllib.request.urlopen(URL, timeout=60).read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024: raise ValueError("Oversize archive")
    archive_path = ROOT / "rag20_agent_pilot_v1.zip"
    archive_path.write_bytes(raw)
    inventory = []
    with zipfile.ZipFile(archive_path) as archive:
        if len(archive.infolist()) > 100 or sum(x.file_size for x in archive.infolist()) > 20 * 1024 * 1024:
            raise ValueError("Oversize archive contents")
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
                raise ValueError("Unsafe archive path")
            if stat.S_ISLNK(item.external_attr >> 16): raise ValueError("Symlink rejected")
            if item.is_dir(): continue
            data = archive.read(item)
            destination = ROOT / "original_contents" / str(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError("Refuse to overwrite original data")
            destination.write_bytes(data)
            entry = {"path":str(destination.relative_to(ROOT)), "bytes":len(data),
                     "sha256":hashlib.sha256(data).hexdigest()}
            if destination.suffix == ".jsonl":
                rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
                entry.update(record_count=len(rows), first_record_keys=list(rows[0]) if rows else [])
            inventory.append(entry)
    report = {"status":"EXACT_ORIGINAL_ARCHIVE_IMPORTED", "source_url":URL,
              "archive_sha256":hashlib.sha256(raw).hexdigest(), "archive_bytes":len(raw),
              "responses_regenerated":False, "inventory":inventory,
              "semantic_support_verified_independently":False}
    (ROOT / "import_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__ == "__main__": main()
