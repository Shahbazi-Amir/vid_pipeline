# Runtime outputs

Pipeline runs write one directory per stable job ID here. Generated transcripts,
normalized media, diagnostics, and review payloads are runtime artifacts and are
not tracked by Git.

The canonical base deliverables are:

- `delivery/transcript.md`
- `delivery/transcript.txt`
- `delivery/transcript.timestamped.md`

Internal `raw/`, `machine/`, `audio/`, `review/`, and `final/` files remain under
the job directory for audit and resume. A semantic review is explicit; it is
never inferred from deterministic cleanup.
