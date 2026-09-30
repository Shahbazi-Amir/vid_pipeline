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
    global ROOT
    base = Path("experiments/rag20/batches")
    catalog = json.loads((base / "index.json").read_text())
    reports = []
    for b in range(5):
        start, end = 171 + b * 100, 270 + b * 100
        folder = f"test_{start}_{end}"
        ROOT = base / folder
        inputs, outputs = rows(ROOT / "inputs.jsonl"), rows(ROOT / "outputs.jsonl")
        manifest = json.loads((ROOT / "manifest.json").read_text())
        count = validate(inputs, outputs, manifest)
        bad = json.loads(json.dumps(outputs))
        next(o for o in bad if o["response"]["claims"])["response"]["claims"][0]["evidence_ids"] = ["not-in-this-prompt"]
        try:
            validate(inputs, bad, manifest)
        except ValueError:
            pass
        else:
            raise ValueError("Negative reference check failed")
        for inp, out in zip(inputs, outputs):
            inp["messages_sha256"] = sha(inp["messages"])
            out["messages_sha256"] = inp["messages_sha256"]
            out["response_sha256"] = sha(out["response"])
        save_rows(ROOT / "inputs.jsonl", inputs)
        save_rows(ROOT / "outputs.jsonl", outputs)
        require(validate(rows(ROOT / "inputs.jsonl"), rows(ROOT / "outputs.jsonl"), manifest) == count, "Reload mismatch")
        empty = sum(not o["response"]["claims"] for o in outputs)
        report = dict(status="STRUCTURAL_AND_LINEAGE_VALIDATION_PASS", candidate_count=100,
                      responses_with_claims=100-empty, empty_claims_count=empty, claim_count=count,
                      unknown_evidence_negative_check="PASS", independent_reload="PASS",
                      semantic_support_verified_independently=False, nb19_nb20_import_ready=False,
                      paid_provider_api_calls=0, gold_label_evaluation="NOT_RUN")
        manifest.update(report)
        manifest["files_sha256"] = {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ("inputs.jsonl","outputs.jsonl")}
        for name, data in (("manifest.json", manifest), ("validation.json", report)):
            (ROOT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")
        package = f"rag_agent_test_{start}_{end}.zip"
        with zipfile.ZipFile(ROOT/package, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("inputs.jsonl","outputs.jsonl","manifest.json","validation.json"):
                z.write(ROOT/name, name)
        reports.append(report)
        catalog["batches"] = [x for x in catalog["batches"] if x["directory"] != folder]
        catalog["batches"].append(dict(batch_number=b+4,positions=[start,end],candidate_count=100,
            status="STORED_STRUCTURAL_AND_LINEAGE_VALIDATION_PASS", directory=folder,
            package=f"{folder}/{package}", **{n:f"{folder}/{n}.jsonl" for n in ("inputs","outputs")},
            manifest=f"{folder}/manifest.json", validation=f"{folder}/validation.json",
            responses_with_claims=100-empty, empty_claims_count=empty))
    all_ids=[]
    for batch in catalog["batches"]:
        ins, outs = rows(base/batch["inputs"]), rows(base/batch["outputs"])
        require(len(ins)==len(outs)==batch["candidate_count"],"Catalog count mismatch")
        require([i["candidate_id"] for i in ins]==[o["candidate_id"] for o in outs],"Catalog pairing mismatch")
        for inp,out in zip(ins,outs):
            allowed={e["evidence_id"] for e in json.loads(inp["messages"][1]["content"])["evidence"]}
            for c in out["response"]["claims"]:
                require(set(c["evidence_ids"]).issubset(allowed),"Catalog unknown evidence")
        all_ids.extend(i["candidate_id"] for i in ins)
    require(len(all_ids)==len(set(all_ids))==670,"Catalog duplicates or missing records")
    require(all_ids==sorted(all_ids),"Catalog ordering mismatch")
    catalog.update(reported_authored_count=670,stored_count=670,next_unused_test_position=671)
    summary=dict(status="STRUCTURAL_AND_LINEAGE_VALIDATION_PASS",candidate_count=500,
                 positions=[171,670],responses_with_claims=sum(r["responses_with_claims"] for r in reports),
                 empty_claims_count=sum(r["empty_claims_count"] for r in reports),
                 semantic_support_verified_independently=False,gold_label_evaluation="NOT_RUN",
                 paid_provider_api_calls=0,isolated_model_requests=0,batches=reports)
    validation=dict(status="PASS",stored_count=670,unique_candidate_count=670,
                    duplicate_candidate_ids=[],candidate_pairing="PASS",evidence_membership="PASS",
                    next_unused_test_position=671,semantic_support_verified_independently=False)
    for name,data in (("index.json",catalog),("catalog_validation.json",validation),("batch_171_670_validation.json",summary)):
        (base/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    with zipfile.ZipFile(base/"rag_agent_test_171_670.zip","w",zipfile.ZIP_DEFLATED) as z:
        z.write(base/"batch_171_670_validation.json","batch_171_670_validation.json")
        for b in range(5):
            folder=f"test_{171+b*100}_{270+b*100}"
            for name in ("inputs.jsonl","outputs.jsonl","manifest.json","validation.json"):
                z.write(base/folder/name,f"{folder}/{name}")
    (base/"README.md").write_text("# RAG agent pilot batches\n\n670 distinct test candidates stored. Next position: 671.\n\n"
        "New positions 171–670 are available as five 100-item packages and rag_agent_test_171_670.zip. "
        "Each contains full supplied evidence, responses, provenance and structural validation.\n\n"
        "These are current ChatGPT/Codex tool-assisted authored responses, not isolated provider inference calls "
        "or frozen Qwen executions. No paid provider API calls. Gold-label evaluation and independent semantic "
        "scoring were not run; NB19/NB20 import readiness is false. Empty claims indicate abstention, not scored failures.\n\n"
        "See index.json for every numbered batch. The original 20-item package remains unchanged.\n")
    print(json.dumps(summary,indent=2))

if __name__ == "__main__":
    main()
