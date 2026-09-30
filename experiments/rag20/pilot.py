"""Validate agent-authored RAG pilot packages. No network or model calls."""

import argparse
import hashlib
import json
from pathlib import Path


def canonical_sha(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_rows(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def validate(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == "rag20_agent_pilot_v1", "Unknown package schema")
    require(manifest["frozen_qwen_execution"] is False, "Must not be a frozen Qwen release")
    require(manifest["nb19_nb20_import_ready"] is False, "No automatic production import")
    require(manifest["semantic_support_verified_independently"] is False,
            "This validator does not verify semantic support")
    for name in ("inputs.jsonl", "outputs.jsonl"):
        require(hashlib.sha256((package / name).read_bytes()).hexdigest()
                == manifest["files_sha256"][name], f"File hash mismatch: {name}")
    inputs = read_rows(package / "inputs.jsonl")
    outputs = read_rows(package / "outputs.jsonl")
    require(len(inputs) == len(outputs) == manifest["candidate_count"] == 20,
            "Expected exactly 20 matching input/output records")
    ids = [row["candidate_id"] for row in inputs]
    require(len(set(ids)) == len(ids) and ids == sorted(ids), "Input IDs must be unique and sorted")
    require(ids == [row["candidate_id"] for row in outputs], "Output identity/order mismatch")
    require(ids == manifest["candidate_ids"], "Manifest identity/order mismatch")
    claim_count = 0
    abstained = 0
    for inp, out in zip(inputs, outputs):
        require(set(inp) == {"candidate_id", "split", "messages", "messages_sha256"},
                "Unexpected input fields")
        require(inp["split"] == "test", "Expected Test split")
        messages = inp["messages"]
        require(len(messages) == 2 and messages[0]["role"] == "system"
                and messages[1]["role"] == "user", "Unexpected message structure")
        require(all(set(m) == {"role", "content"} for m in messages), "Unexpected message fields")
        require(canonical_sha(messages) == inp["messages_sha256"], "Prompt hash mismatch")
        require(hashlib.sha256(messages[0]["content"].encode("utf-8")).hexdigest()
                == manifest["system_prompt_sha256"], "System prompt hash mismatch")
        payload = json.loads(messages[1]["content"])
        require(set(payload) == {"question", "evidence", "response_schema"}, "Unexpected payload fields")
        require(isinstance(payload["question"], str) and payload["question"].strip(), "Empty question")
        require(canonical_sha(payload["response_schema"]) == manifest["response_schema_sha256"],
                "Response schema hash mismatch")
        evidence = payload["evidence"]
        require(isinstance(evidence, list) and 8 <= len(evidence) <= 10, "Unexpected evidence count")
        evidence_ids = []
        for row in evidence:
            require(set(row) == {"evidence_id", "text"}, "Unexpected evidence fields")
            require(all(isinstance(row[k], str) and row[k].strip() for k in row), "Empty evidence field")
            evidence_ids.append(row["evidence_id"])
        require(len(set(evidence_ids)) == len(evidence_ids), "Duplicate evidence ID")
        require(set(out) == {"candidate_id", "messages_sha256", "response", "response_sha256"},
                "Unexpected output fields")
        require(out["messages_sha256"] == inp["messages_sha256"], "Output prompt lineage mismatch")
        response = out["response"]
        require(canonical_sha(response) == out["response_sha256"], "Response hash mismatch")
        require(set(response) == {"answer_text", "claims"}, "Unexpected response fields")
        require(isinstance(response["answer_text"], str) and response["answer_text"].strip(), "Empty answer")
        require(isinstance(response["claims"], list), "Claims must be an array")
        abstained += int(not response["claims"])
        for claim in response["claims"]:
            require(set(claim) == {"claim_text", "claim_type", "evidence_ids"}, "Unexpected claim fields")
            require(all(isinstance(claim[k], str) and claim[k].strip()
                        for k in ("claim_text", "claim_type")), "Invalid claim text/type")
            refs = claim["evidence_ids"]
            require(isinstance(refs, list) and refs and all(isinstance(x, str) for x in refs),
                    "Claim must have evidence IDs")
            require(len(set(refs)) == len(refs) and set(refs).issubset(evidence_ids),
                    "Claim references evidence outside its prompt")
            claim_count += 1
    require(claim_count == manifest["claim_count"] and abstained == manifest["empty_claims_count"],
            "Manifest counts mismatch")
    return {"status": "STRUCTURAL_AND_LINEAGE_VALIDATION_PASS", "candidate_count": len(inputs),
            "claim_count": claim_count, "empty_claims_count": abstained,
            "semantic_support_verified": False, "frozen_qwen_execution": False,
            "nb19_nb20_import_ready": False, "api_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Directory containing inputs, outputs and manifest")
    args = parser.parse_args()
    print(json.dumps(validate(args.package), ensure_ascii=False, indent=2))
