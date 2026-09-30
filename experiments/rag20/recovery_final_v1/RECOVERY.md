# Recovery protocol v2

This is an intermediate AGENT_REVIEW checkpoint, not NB19/NB20 import output.
No model API is used. Work stays inside vid_pipeline recovery_final_v1.

1. Fetch this checkpoint commit or extract its ZIP into
   `vid_pipeline/experiments/rag20/recovery_final_v1`.
2. The ZIP deliberately excludes unchanged large input/output aggregates.
   Fetch the 26 exact batch files listed in DEPENDENCIES.json from
   Shahbazi-Amir/vid_pipeline commit
   `ebfadb00263a18af5dbd53931f18b434a7c7acb1` at their original paths.
   Check each SHA256 (and Git blob SHA). Use an authorized GitHub connector
   or a pinned checkout. Do not substitute another branch's current files.
3. Run `python experiments/rag20/recovery_final_v1/rebuild_fixed_sources.py`.
   This deterministically rebuilds only inputs.jsonl and outputs.jsonl;
   it requires no source_cache or Gold and never changes review decisions.
4. Run `python experiments/rag20/recovery_final_v1/incremental_review.py --restore`.
   CURRENT references the authoritative immutable checkpoint generation.
   Its hashes are checked first; interrupted root mirrors are repaired from
   that generation. Run `verify_recovery.py` for read-only verification.
5. Continue at CURRENT.next_semantic_position. Read question, complete evidence,
   active response and every claim; write explicit candidate-specific decisions.
   append_decisions merges unique IDs; an identical replay is a no-op, a conflicting
   decision needs an explicit next revision, and old repair records are immutable.
6. publish stages all mutable files, validates/reloads them, checks against prior
   IDs and revisions, renames the independent generation, atomically updates CURRENT,
   then restores root mirrors. A crash before the CURRENT update leaves the preceding
   generation authoritative; after the update, --restore completes publication.
   A leftover `.staging` directory is uncommitted and must not be counted as progress.
   Use a fresh unique checkpoint name for each publication; never overwrite one.

The bootstrap semantic_batch_001_005.py now preserves any existing review and repair
files. It cannot be used to erase later progress. decision scripts are explicit
recordings of these particular reviews, not a rule for unseen candidates. For an
identical re-run, append_decisions is idempotent; publish refuses an existing
checkpoint name. Do not re-run audit_structure.py during semantic continuation:
its fixed source_cache dependencies and validation rewrite belong to the earlier
structural phase. No structural re-audit was performed in this continuation.

Independent source/location validation is NOT_RUN: original source documents have
not been matched to citation metadata. The cached metadata is not proof of location.
NB19 adapter, full validation/handoff and NB20 are also NOT_RUN. Five legacy reviews
remain preserved; the new answer-unit coverage contract has not been retroactively
claimed for them. Complete those fields before final import. REVIEW_REQUIRED is a
completed review requiring resolution; unreviewed rows have NOT_EVALUATED semantics.

Timing correction: 23:12 UTC in the first v2 checkpoint was not an instrumented
start and must not be used for rates. The first observed clock is
2026-09-30T23:16:54Z. The original turn start was not recorded. The next checkpoint
completed at 23:21:37Z (5 reviews in 4m43s including revision/validation work).
Estimate remains provisional until packaging is complete; it is active working
time, not unattended execution or a promised deadline.
