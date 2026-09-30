# RAG agent batches

Numbered pilot outputs on `agent/rag-evidence-shards` in `Shahbazi-Amir/vid_pipeline`.

| Batch | Sorted Test positions | Count | Folder | Status |
| --- | --- | ---: | --- | --- |
| 001 | 001–020 | 20 | [test_001_020](test_001_020/) | Exact original release ZIP imported; responses preserved |
| 002 | 021–070 | 50 | [test_021_070](test_021_070/) | Stored; structural and lineage validation passed |
| 003 | 071–170 | 100 | [test_071_170](test_071_170/) | Stored; structural and lineage validation passed |

Downloads:
- [Original 20-record package](test_001_020/rag20_agent_pilot_v1.zip)
- [50-record package](test_021_070/rag_agent_test_021_070.zip)
- [100-record package](test_071_170/rag_agent_test_071_170.zip)

Batch 001 preserves the original ZIP byte-for-byte and all extracted files under
`original_contents/`; `import_report.json` records hashes. Its responses were not regenerated.
Batches 002 and 003 each contain `inputs.jsonl`, `outputs.jsonl`, `manifest.json`,
`validation.json`, and the downloadable ZIP. Complete supplied evidence is preserved in inputs.

Stored outputs: **170**. Next unused sorted Test position: **171**.
Batch 003 contains 89 responses with claims and 11 abstentions or ambiguity responses.
These numbers are output counts, not accuracy scores.
[Catalog validation](catalog_validation.json) checks structure, hashes, lineage,
ordering and absence of duplicate candidate IDs across the three batches.

Each future batch must use a new range-named folder and update `index.json`.
No concatenation has been performed.
Current ChatGPT/Codex agent authored these exploratory responses using supplied
evidence through tools. They are not isolated model executions, frozen Qwen runs,
independently verified semantic answers, or NB19/NB20 import-ready releases.
No paid provider inference API was called. GitHub Actions usage and subscription
costs are not measured. Golden reference answers and accuracy metrics were not used.
RAG_finance was read only; all artifacts and workflows were stored in vid_pipeline.
