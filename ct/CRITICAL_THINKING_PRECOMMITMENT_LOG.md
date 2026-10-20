# Critical Thinking + AEL Task Precommitment — Development Log

**Working branch:** `feat/critical-thinking-task-precommitment-v2.9`  
**Target:** AEL Runtime Prototype V2.9.0 (target only; do not describe as released until implementation and tests warrant it)  
**Status:** Precommitment recorded before implementation.  
**Date:** 2026-10-20  
**Authority boundary:** The author supplied the source AEL materials and the desired capability. This log's coding and integration choices are the implementation agent's responsibility, not decisions delegated to the author for technical approval.

## Entry 000 — User requirement and implementation interpretation

### Requirement supplied by the author

AEL originates in critical thinking. Its survival-oriented form is a minimal practical critical-thinking behaviour. The earlier AEL runtime was an attempt to simulate biological AEL mechanisms because a bot at that time could not reliably carry the process itself.

With stronger critical thinking, AEL may become more task-oriented: an AI bot should do more of the investigative and implementation work autonomously, while AEL continues governing the boundaries and preserving accountability. It should return an inspectable record rather than push all the verification burden back onto the human.

For a task requested by a user, the intended high-level sequence is:

1. The bot receives the task.
2. It conducts its own critical-thinking investigation.
3. It presents detailed case notes supporting its understanding and proposed direction.
4. The user can approve or reject those case notes.
5. The bot presents an implementation plan and the evidence-based case for that plan.
6. The user can approve or reject the plan.
7. Execution is allowed only after both approvals apply to the exact submitted versions.
8. The bot returns the requested work together with an auditable record of its actions, deviations, results and verification limits.

This is a precommitment mechanism: the bot bears the burden of producing its case and plan before execution. Approval is not a declaration that the case is true; it authorises proceeding on the submitted grounds. New evidence may require revision and renewed approval.

### Interpretation used for this implementation

Implement task-level precommitment as a distinct lifecycle alongside existing AEL primitives. Reuse the existing append-only event ledger and preserve the distinction between historical records and active influence. The approved case and approved implementation plan must be represented by immutable, hash-identified artifacts. Decisions bind to those exact hashes.

This is an extension of the runtime implementation, not a rewrite or reinterpretation of the author's canonical AEL sources. The critical-thinking skill supplies inquiry behaviours; it does not replace AEL's external controls.

## Entry 001 — Starting-state inspection

The following repository files were inspected before implementation:

- `README.md`
- `VERSION.md`
- `DESIGN_ALIGNMENT.md`
- `NEXT_STEPS.md`
- `SOURCES.md`
- `EVIDENCE_RECONCILIATION.md`
- `MODEL_INPUT_BOUNDARY.md`
- `CONTEXT_BUDGET_POLICY.md`
- `MEMORY_WORKFLOW.md`
- `DELTA_FIRST_DELIVERY.md`
- `USAGE_DISPOSITION.md`
- `runtime.py`
- `tests/test_runtime.py`
- `.github/workflows/tests.yml`
- `AUTHORS_NOTE.md`
- `OWNERSHIP_AND_LICENSE.md`

### Existing mechanisms to preserve

The current V2.8.1 prototype has an append-only event ledger; a disposable active-context projection; controls for rejected branch output; separate provenance, decision authority, truth status and inference kind; retention/use separation; explicit branch choices; immutable revision proposals; hash-bound revision approval; post-expansion textual-scope verification; a strict model-input allowlist; and a loopback-only local Ollama adapter.

The current tests cover 57 unit-test cases, including mock-server tests. The repository's own status documents say that real Ollama inference was not run in its development environment. Textual revision conformance is not semantic correctness, and the prototype does not currently connect directly to ChatGPT/Claude websites or provide a general arbitrary-app execution layer.

### Missing capability relevant to this change

There is no task-level lifecycle binding (a) a critical-thinking case, (b) the implementation plan derived from that case, (c) user approval of each exact artifact, (d) execution records and deviations, and (e) a final verification record into one auditable task.

The existing revision lifecycle is narrower: it governs proposing and applying a document revision. It should not be overloaded to represent an entire autonomous task.

## Entry 002 — Critical-thinking dependency provenance

The skill source inspected is:

- Repository: https://github.com/memoryprismv1/cognitive-interface-ai-skills
- Path: `critical-thinking/SKILL.md`
- Upstream main commit at precommitment time: `d1f23e2ad9dafd323940fc6b7a00f1700275d885`
- Source blob SHA: `d7134969b124e39c04e343bed2ce2475f64b9a64`
- Source file: https://github.com/memoryprismv1/cognitive-interface-ai-skills/blob/d1f23e2ad9dafd323940fc6b7a00f1700275d885/critical-thinking/SKILL.md
- Source license: CC BY-NC 4.0, with attribution and other license obligations.

The dependency should be pinned to this identifiable snapshot for reproducibility, with upstream origin, commit, blob/content hash and license/attribution retained in the package. Updating the source skill must be an explicit dependency update, not a silent fetch from the moving `main` branch.

The source skill is provisional. Pinning it makes the dependency reproducible; it does not validate the skill as a reliable or generally transferable capability. It must be used as flexible inquiry guidance, not transformed into a compulsory form for every interaction.

## Entry 003 — Proposed implementation plan (committed before code changes)

### A. Add a reproducible skill dependency

1. Include the skill snapshot at its pinned upstream revision.
2. Add dependency provenance and licensing/attribution information.
3. Make the autonomous task-precommitment path consume the pinned skill explicitly.
4. Record the dependency version/hash with each task so that its governing instructions can later be identified.
5. Do not silently inject a large research protocol into unrelated legacy runtime operations merely because the dependency exists.

### B. Add a separate task-precommitment state machine

The lifecycle should distinguish at least:

- task created;
- case notes submitted;
- case notes approved or rejected;
- implementation plan submitted;
- implementation plan approved or rejected;
- execution authorised and started;
- execution completed, blocked, or stopped;
- verification report recorded.

Approval must be attached to the exact immutable artifact hash. A replacement case invalidates approval of the previous case and any plan based on it. A replacement plan invalidates the former plan approval. Execution must fail closed unless both the current case and current plan are approved and the plan is bound to that exact case.

A rejection must be recorded, not erased. A rejected artifact must not be treated as the active approved case or plan.

### C. Return a task audit package

The record should connect the initial request and constraints; critical-thinking dependency identity; case notes; plan; hash-bound decisions; execution events; deviations; outputs; checks performed; and outstanding verification limits.

The report must distinguish runtime-observed events and computed hashes from assertions supplied by a model. A status label such as “verified” must not be treated as proof without a recorded check or supporting artifact. The runtime can enforce presence, sequencing and identity of records; it cannot independently establish semantic truth merely by storing a model's report.

### D. Test the control boundary

Add tests for:

- execution blocked before case approval;
- execution blocked before plan approval;
- stale approvals not authorising changed artifacts;
- a plan linked to a different case being rejected;
- rejected artifacts remaining historical but not becoming current approvals;
- every approval and execution transition being auditable;
- final reports carrying the actual artifact hashes and stated verification status;
- dependency identity appearing in the task record;
- legacy runtime behavior and the existing test suite remaining intact.

### E. Keep the scope honest

This implementation can provide auditable task records and enforce approval state within the runtime API. It must not claim to physically prevent an external agent from acting outside the runtime, to perform actions in arbitrary websites/apps, or to prove that reasoning is correct simply because its protocol ran.

The current local Ollama bridge is text-chat only. A general executor/tool adapter remains a separate future integration. The first deliverable should make the precommitment contract concrete and testable without claiming that missing action-execution capabilities already exist.

## Entry 004 — Precommitted success criteria

Implementation will be considered locally successful only if:

1. The source skill is pinned and the exact dependency identity is auditable.
2. The task protocol refuses execution until both applicable approvals exist.
3. Both approvals are bound to the current immutable artifact hashes.
4. Revisions cannot inherit approvals for earlier content.
5. The audit export allows a reviewer to reconstruct the task's recorded lifecycle without relying solely on the model's summary.
6. Automated tests exercise successful and adversarial state transitions.
7. Existing AEL tests and documented boundaries remain intact.
8. Documentation distinguishes implemented control flow from future autonomous execution and from semantic verification.

Test success validates only the tested implementation behavior. It does not establish autonomous critical-thinking competence or the correctness of every claim produced by a model.

## Entry 005 — Execution results

**Not yet started at the time this precommitment entry was committed.** Results, deviations from this plan, failures, fixes, and remaining gaps will be appended after implementation. This section must not be backfilled to imply that precommitment followed the work.
