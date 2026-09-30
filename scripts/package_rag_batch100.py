"""Check and package the 100 agent-authored pilot records; no inference or API."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path("experiments/rag20/batches/test_071_170")


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
    require(len(inputs) == len(outputs) == manifest["candidate_count"] == 100, "Count mismatch")
    ids = [x["candidate_id"] for x in inputs]
    require(len(set(ids)) == 100 and ids == sorted(ids), "Duplicate or unordered input IDs")
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
    inputs, outputs = rows(ROOT / "inputs.jsonl"), rows(ROOT / "outputs.jsonl")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    count = validate(inputs, outputs, manifest)
    # Negative check: a fabricated reference must fail even with syntactically valid JSON.
    bad = json.loads(json.dumps(outputs))
    bad[0]["response"]["claims"][0]["evidence_ids"] = ["not-in-this-prompt"]
    try:
        validate(inputs, bad, manifest)
    except ValueError:
        pass
    else:
        raise ValueError("Unknown-evidence negative check failed")
    for inp, out in zip(inputs, outputs):
        inp["messages_sha256"] = sha(inp["messages"])
        out["messages_sha256"] = inp["messages_sha256"]
        out["response_sha256"] = sha(out["response"])
    save_rows(ROOT / "inputs.jsonl", inputs)
    save_rows(ROOT / "outputs.jsonl", outputs)
    require(validate(rows(ROOT / "inputs.jsonl"), rows(ROOT / "outputs.jsonl"), manifest)
            == count, "Reload validation mismatch")
    empty = sum(not o["response"]["claims"] for o in outputs)
    report = {"status": "STRUCTURAL_AND_LINEAGE_VALIDATION_PASS", "candidate_count": 100,
              "responses_with_claims": 100 - empty, "empty_claims_count": empty, "claim_count": count,
              "unknown_evidence_negative_check": "PASS", "independent_reload": "PASS",
              "semantic_support_verified_independently": False, "nb19_nb20_import_ready": False,
              "paid_provider_api_calls": 0}
    manifest.update(report)
    manifest["files_sha256"] = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
                               for n in ("inputs.jsonl", "outputs.jsonl")}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
    (ROOT / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(ROOT / "rag_agent_test_071_170.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("inputs.jsonl", "outputs.jsonl", "manifest.json", "validation.json"):
            archive.write(ROOT / name, name)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
