# Rooted revision artifact provenance

File-backed revisions use the shared runtime to read the source artifact. The caller supplies an explicit workspace root and a workspace-relative path; the runtime rejects absolute paths, parent traversal, and symlinks that resolve outside the workspace. It reads exact bytes, requires UTF-8 text, and hashes those bytes, preserving CRLF/LF distinctions.

The proposal stores the normalized relative path, exact-byte SHA-256, and byte length in the immutable revision proposal. The initial revision event retains the same source provenance. Expansion re-reads the pinned relative path under the supplied workspace root and refuses to expand if the file is unavailable or its hash changed after review. The failed attempt is retained as a revision event without advancing the proposal state.

Verification re-reads the same pinned file. A changed source produces a failed conformance result; a missing, unreadable, invalid-UTF-8, or unsafe source produces an unverifiable result. Both outcomes fail closed for release readiness and are retained in conformance history and revision events. Successful expansion and verification retain the relative path, observed hash, byte length, and validation result.

## Python API

```python
from pathlib import Path
import runtime

con = runtime.connect("ael.sqlite3")
workspace = Path("workspace")

preview = runtime.propose_revision_from_file(
    con,
    workspace_root=workspace,
    source_path="docs/report.md",
    account="default",
    project="project-name",
    chat="chat-id",
    proposal_id="revision-001",
    artifact_id="docs/report.md",
    base_version="v1",
    original_request="Revise the report while preserving its core claims.",
    delta_summary="Clarify the methodology section.",
    impact_summary="Methodology only; findings and references remain unchanged.",
    changed_sections=["heading:Report / Methodology"],
)

runtime.decide_revision(con, "revision-001", "accept", account="default")
candidate = Path("candidate-report.md").read_text(encoding="utf-8")

runtime.expand_revision_from_file(
    con, "revision-001", workspace_root=workspace,
    artifact_version="v2", content=candidate, account="default",
)

report = runtime.verify_revision_output_from_file(
    con, "revision-001", workspace_root=workspace, account="default",
)
```

The existing `propose_revision`, `expand_revision`, and `verify_revision_output` APIs remain available for compatibility. They retain their existing caller-supplied content/hash behavior and do not claim rooted provenance. New file-backed workflows should use `propose_revision_from_file`, `expand_revision_from_file`, and `verify_revision_output_from_file`.

## Security boundary

This is a runtime path and provenance guard, not an OS sandbox. Another process with write access to the workspace may still modify files concurrently; callers should use an appropriately controlled workspace during proposal, expansion, and verification. The mechanism verifies byte identity and textual changed-section scope, not semantic correctness of generated content.
