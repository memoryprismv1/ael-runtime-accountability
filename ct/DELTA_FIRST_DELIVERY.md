# Mechanism 10 — Delta-First Delivery

**Status:** Local state-machine prototype, covered by unit tests. Not connected to a live model or artifact editor.

## Principle

For revisions to existing work, expose the cheap structural delta before generating or asking the user to inspect the expensive full artifact.

`revision request → structural delta + impact → explicit accept/reject`

- **Accept:** authorize expansion of the exact immutable proposal that was reviewed.
- **Reject:** keep the rejected proposal in history, reset the plan, and re-plan from the original request, stable artifact basis, current stable context and the user's correction signal. Do not feed the rejected delta or impact text into the fresh plan.

## States

`proposed → accepted_for_expansion → expanded`

`proposed → rejected → rejected_reset`

An accepted proposal can still be rejected before expansion if the user changes their mind. A rejected/reset proposal cannot be accepted or expanded; it is a parent for a new proposal with a fresh ID and hash. The prior acceptance does not transfer to the child proposal.

## Stored data

Each proposal stores:

- unique proposal ID and scope (account/project/chat);
- artifact ID, base version, optional base SHA-256 and source reference;
- the original request;
- delta summary, impact summary and changed sections;
- an immutable proposal hash;
- an append-only decision/state history.

An expanded output is separately stored with a content SHA-256 and a link to the exact approved proposal hash. Proposal, revision-event, and output history is protected against SQL updates/deletes by triggers.

## Path-rooted file integration (preferred)

The \`revision propose-file\`, \`revision expand-file\`, and \`revision verify-file\` commands make the runtime load the source itself instead of trusting a caller-supplied hash or base text.

- \`propose-file\` resolves \`--artifact-file\` beneath \`--workspace-root\`, reads the original UTF-8 bytes, computes SHA-256, and records the resolved workspace-relative source path and hash with the immutable proposal.
- \`expand-file\` reloads that same source path and refuses expansion if the bytes no longer match the approved base. It also loads generated content from a separate file beneath the same root and records that path/hash in the append-only expansion event.
- \`verify-file\` reloads the pinned source again and records the path and observed base hash in the conformance report. If the bytes changed, verification fails and output is not release-ready.
- Absolute artifact paths, parent-directory traversal, non-UTF-8 files, and symlinks resolving outside the workspace root are rejected.

Use workspace-relative paths. The older low-level commands remain available for compatibility, but caller-supplied hash/content pairs do not provide the same source-provenance guarantee. This file boundary is not a sandbox against another process with filesystem access and does not establish semantic correctness.

### File-backed CLI walkthrough

\`\`\`bash
python runtime.py --db data/ael.sqlite3 revision propose-file \\
  --project memory-prism --chat essay-edit-001 --id intro-change-01 \\
  --workspace-root ./workspace --artifact-file essays/essay.md --base-version v1 \\
  --original-request "Revise the introduction while preserving the central thesis." \\
  --delta-summary "Clarify the opening and foreground the thesis." \\
  --impact-summary "Opening changes; body sections and references should remain stable." \\
  --changed-section "heading:Essay / Introduction"
\`\`\`

After reviewing and accepting the delta, save the proposed expansion to a separate file inside the workspace and run:

\`\`\`bash
python runtime.py --db data/ael.sqlite3 revision expand-file \\
  --id intro-change-01 --workspace-root ./workspace --content-file drafts/essay-v2.md --artifact-version v2

python runtime.py --db data/ael.sqlite3 revision verify-file \\
  --id intro-change-01 --workspace-root ./workspace
\`\`\`

The source path is taken from the proposal record; expansion and verification re-read it rather than accepting a replacement path from the caller.

## Base-artifact protection

## CLI walkthrough

Create a proposal. No full artifact is generated at this stage:

```bash
python runtime.py --db data/ael.sqlite3 revision propose \
  --project memory-prism --chat essay-edit-001 \
  --id intro-change-01 --artifact-id essay.md --base-version v1 \
  --base-sha256 ACTUAL_BASE_SHA256 \
  --original-request "Revise the introduction while preserving the central thesis." \
  --delta-summary "Clarify the opening and move the thesis statement into the first paragraph." \
  --impact-summary "Opening is more direct; later sections and references remain unchanged." \
  --changed-section Introduction Opening
```

Inspect the proposal:

```bash
python runtime.py --db data/ael.sqlite3 revision show --id intro-change-01
```

If the proposed direction is right, accept it explicitly:

```bash
python runtime.py --db data/ael.sqlite3 revision decide --id intro-change-01 --decision accept --note "Delta matches the intended direction"
```

Only after the acceptance should the expanded artifact be supplied. `expanded.md` is a file generated after approval; `ACTUAL_BASE_SHA256` must still match the base hash used for the proposal:

```bash
python runtime.py --db data/ael.sqlite3 revision expand --id intro-change-01 \
  --artifact-version v2 --content-file expanded.md \
  --current-base-sha256 ACTUAL_BASE_SHA256
```

If the delta is wrong, reject it with a concise correction:

```bash
python runtime.py --db data/ael.sqlite3 revision decide --id intro-change-01 \
  --decision reject --note "Wrong direction; preserve the original order and only clarify the thesis."
```

Inspect the clean re-plan basis, which deliberately omits the rejected delta and its impact summary:

```bash
python runtime.py --db data/ael.sqlite3 revision replan-context \
  --id intro-change-01 --project memory-prism --chat essay-edit-001
```

Then create a new proposal from the original request and stable artifact basis:

```bash
python runtime.py --db data/ael.sqlite3 revision replan \
  --project memory-prism --chat essay-edit-001 \
  --from-id intro-change-01 --id intro-change-02 \
  --delta-summary "Keep original order; clarify only the thesis sentence." \
  --impact-summary "Limited edit; existing structure and references remain intact." \
  --changed-section Introduction
```

The child proposal inherits the original request and artifact identity from the rejected parent, but not the rejected delta. It requires its own explicit acceptance.

## Invariants tested

- No full artifact can be expanded before acceptance.
- An acceptance binds to the immutable proposal hash.
- An existing proposal ID cannot be reused to smuggle in a changed delta.
- A recorded base hash must match before expansion.
- Rejecting a proposal records the user's correction signal and triggers a reset state.
- Re-plan context contains original request, stable context and correction signal, but not the rejected delta or impact summary.
- Re-plan is allowed only from a `rejected_reset` proposal.
- An accepted proposal may be rejected before expansion; after rejection, expansion is blocked.
- Proposal, decision, and expanded-output records remain immutable history.

## Limits

This is a local Python/SQLite workflow, not yet a human-facing UI. A user or calling agent must prepare a truthful delta and impact summary; the runtime does not generate those summaries by itself and does not verify that a full artifact substantively follows them. That requires a later artifact diff/integration check. The state machine makes the decision point and exact approved proposal traceable; it does not guarantee the quality of generated content.
