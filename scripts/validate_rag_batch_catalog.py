"""Check and package the 50 agent-authored pilot records; no inference or API."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path("experiments/rag20/batches/test_021_070")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_rows(path, items):
    path.write_text("".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n"
                           for x in items), encoding="utf-8")


def validate(inputs, outputs, manifest):
    require(len(inputs) == len(outputs) == manifest["candidate_count"] == manifest["candidate_count"], "Count mismatch")
    ids = [x["candidate_id"] for x in inputs]
    require(len(set(ids)) == manifest["candidate_count"] and ids == sorted(ids), "Duplicate or unordered input IDs")
    require(ids == [x["candidate_id"] for x in outputs] == manifest["candidate_ids"], "ID mismatch")
    count = 0
    for inp, out in zip(inputs, outputs):
        require(inp["split"] == "test", "Split mismatch")
        messages = inp["messages"]
        require(len(messages) == 2 and messages[0]["role"] == "system"
                and messages[1]["role"] == "user", "Invalid messages")
        require(hashlib.sha256(messages[0]["content"].encode()).hexdigest()
                == manifest["system_prompt_sha256"], "System template mismatch")
        payload = json.loads(messages[1]["content"])
        require(set(payload) == {"question", "evidence", "response_schema"}, "Unexpected payload fields")
        require(isinstance(payload["question"], str) and payload["question"].strip(), "Empty question")
        require(sha(payload["response_schema"]) == manifest["response_schema_sha256"], "Schema mismatch")
        evidence = payload["evidence"]
        require(8 <= len(evidence) <= 10, "Evidence count mismatch")
        for e in evidence:
            require(set(e) == {"evidence_id", "text"} and all(isinstance(v, str) and v.strip()
                    for v in e.values()), "Invalid evidence")
        allowed = {e["evidence_id"] for e in evidence}
        require(len(allowed) == len(evidence), "Duplicate evidence")
        response = out["response"]
        require(set(response) == {"answer_text", "claims"}, "Invalid response fields")
        require(isinstance(response["answer_text"], str) and response["answer_text"].strip(), "Empty answer")
        require(isinstance(response["claims"], list), "Invalid claims")
        for c in response["claims"]:
            require(set(c) == {"claim_text", "claim_type", "evidence_ids"}, "Invalid claim fields")
            require(all(isinstance(c[k], str) and c[k].strip() for k in ("claim_text", "claim_type")),
                    "Invalid claim text")
            refs = c["evidence_ids"]
            require(isinstance(refs, list) and refs and all(isinstance(e, str) for e in refs),
                    "Invalid references")
            require(len(set(refs)) == len(refs) and set(refs).issubset(allowed), "Unknown evidence")
            count += 1
        prompt_hash, response_hash = sha(messages), sha(response)
        require(inp.get("messages_sha256", prompt_hash) == prompt_hash, "Input hash mismatch")
        require(out.get("messages_sha256", prompt_hash) == prompt_hash, "Output lineage mismatch")
        require(out.get("response_sha256", response_hash) == response_hash, "Response hash mismatch")
    return count


def main():
    base = Path("experiments/rag20/batches")
    specs = [("test_001_020/original_contents",20),("test_021_070",50),("test_071_170",100)]
    seen = []
    reports = []
    for folder, expected in specs:
        root = base / folder
        inputs, outputs = rows(root / "inputs.jsonl"), rows(root / "outputs.jsonl")
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        require(manifest["candidate_count"] == expected,"Unexpected batch size")
        claims = validate(inputs,outputs,manifest)
        for name, expected_hash in manifest.get("files_sha256",{}).items():
            require(hashlib.sha256((root / name).read_bytes()).hexdigest()==expected_hash,"File hash mismatch")
        seen.extend(x["candidate_id"] for x in inputs)
        reports.append({"directory":folder,"candidate_count":expected,"claim_count":claims})
    require(len(seen)==len(set(seen))==170,"Duplicate candidates across batches")
    require(seen==sorted(seen),"Global order mismatch")
    report={"status":"ALL_THREE_BATCHES_STRUCTURAL_AND_LINEAGE_PASS","stored_count":170,
            "unique_candidate_count":170,"cross_batch_duplicates":0,"batches":reports,
            "semantic_support_verified_independently":False,"gold_label_evaluation":"NOT_RUN"}
    (base / "catalog_validation.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__ == "__main__": main()
