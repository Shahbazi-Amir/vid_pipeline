# RAG agent batches

This directory collects numbered pilot batches on the `agent/rag-evidence-shards`
branch of `Shahbazi-Amir/vid_pipeline`.

| Batch | Sorted Test positions | Count | Location | Repository storage |
| --- | --- | ---: | --- | --- |
| 001 | 001–020 | 20 | Original package `rag20_agent_pilot_v1.zip` delivered in the conversation | Not yet imported |
| 002 | 021–070 | 50 | [test_021_070](test_021_070/) | Stored and structurally validated |

Download batch 002: [rag_agent_test_021_070.zip](test_021_070/rag_agent_test_021_070.zip).

Each stored batch keeps `inputs.jsonl`, `outputs.jsonl`, `manifest.json`,
`validation.json`, and a ZIP package in its own range-named folder.
Batch ordinals are assigned in this index; candidate IDs remain authoritative.

Import the original batch 001 package into `test_001_020/` before marking it
stored. Do not regenerate or silently substitute its original responses.
The original 20-item ZIP has not been uploaded to the inspected release either.

The next unused sorted Test position is 071. For each subsequent batch, add a new
range-named folder and one entry to `index.json` and this table. Never overwrite a
previous batch or duplicate candidate IDs. Before eventual concatenation, check
the candidate sets and prompt lineage across every package.

Reported authored outputs: 70. Outputs stored in this directory: 50.
No concatenation has been performed. Structural validation is not independent
semantic evaluation; these outputs are not frozen Qwen runs or NB19/NB20 releases.
RAG_finance is only a source and is not modified by this organization.
