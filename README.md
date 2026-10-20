# AEL Runtime Prototype V2.8.1 — Local Chat + Conformance

**Status:** V2.8.1 remains the main-branch baseline. The separate V2.9 task-precommitment feature branch is experimental and not a complete AEL runtime or production specification.

AEL and its source framework remain the user's work. This package tests implementation correspondence to the user's source documents; it does not replace them or claim authorship of the framework.

## Public-review staging and ownership

This repository is a public-review prototype. AEL belongs to its author; this implementation is an engineering experiment and does not replace or claim authorship of the original framework. The software implementation is offered under the [PolyForm Noncommercial License 1.0.0](LICENSE). This is source-available, not an OSI-approved open-source license. The license applies only to the implementation material the licensor is entitled to license; it does not grant rights to the original AEL essays, framework publications, or linked source pages. See [LICENSE_STATUS.md](LICENSE_STATUS.md) and [OWNERSHIP_AND_LICENSE.md](OWNERSHIP_AND_LICENSE.md) for the intended scope.

## V2.8.1 addition: interactive local Ollama chat

The runtime includes `ollama-chat`, a standard-library HTTP adapter for a **local Ollama server**, plus `ael_chat.py`, an interactive multi-turn shell that reuses the same persistent event ledger. `ollama-status` checks the local service and lists local models without sending a prompt. By default, the database and audit trail live in a stable per-user data directory outside the versioned program folder; `AEL_RUNTIME_HOME` can override it. It uses no paid API token and refuses non-loopback endpoints by default. The request is built only from the allowlisted `working_context` and `current_user_message`; the audit sidecar, full history, omitted-event details, rejected artifacts, and memory diagnostics are not serialized to the model.

Each call stores the user request and returned assistant response in the persistent event ledger, emits a response JSON file, and writes the runtime audit to a separate file. The runtime rejects identical response/audit destinations so one cannot overwrite the other.

The bridge has been tested end-to-end against a local mock server that implements Ollama's documented non-streaming `/api/chat` response shape. **Ollama is not installed in this development environment, so no real model inference was run here.** The code is ready for a local Ollama installation and a model available on that machine; actual model latency, answer quality and model-specific token counting remain untested.

See [`LOCAL_MODEL_BRIDGE.md`](LOCAL_MODEL_BRIDGE.md) for optional setup and the interactive launcher (`START_AEL_CHAT.bat` on Windows).

## Candidate V2.9 extension: task-level critical-thinking precommitment

**Status:** Experimental feature branch; not yet a released or validated autonomous executor.

The candidate task workflow pins a snapshot of the Critical Thinking skill from the [cognitive-interface-ai-skills repository](https://github.com/memoryprismv1/cognitive-interface-ai-skills). Source commit, Git blob, source license, and the bundled skill's SHA-256 are recorded. The local copy is checked against its Git blob SHA at runtime; updates are explicit rather than silently tracking the upstream default branch.

The task lifecycle stores immutable case-note and implementation-plan artifacts, records approval decisions against their exact SHA-256 hashes, requires the implementation plan to name the approved case hash, and refuses the execution-start transition unless both current artifacts are approved. Replacing case notes clears the current plan. Actions and verification checks are stored as records, and a standalone Markdown audit export includes the artifacts, decisions, actions, evidence references, and event chronology.

The local Ollama commands can generate case notes and plans using the pinned skill. The human must inspect and approve the generated case and plan. The task lifecycle records execution authorisation and supplied action records; **it does not yet execute arbitrary external tasks or prevent an agent from acting outside the runtime**. The audit report is evidence of what the runtime recorded, not proof that model-generated claims are true.

See [the precommitment development log](CRITICAL_THINKING_PRECOMMITMENT_LOG.md) and [the task workflow implementation](ael_task_precommitment.py).

### Example CLI sequence

Run from the repository folder. Use an installed local model name shown by \`python runtime.py ollama-status\`.

\`\`\`bash
python runtime.py task create --project demo --chat task-001 --id task-001 --request "Investigate X and carry out the approved work" --model LOCAL_MODEL
python runtime.py task generate-case --project demo --chat task-001 --id task-001 --model LOCAL_MODEL --out handoffs/task-001-case.md
# Inspect the case notes, then approve or reject them.
python runtime.py task decide-case --project demo --chat task-001 --id task-001 --decision approve --note "Reviewed current case artifact"
python runtime.py task generate-plan --project demo --chat task-001 --id task-001 --model LOCAL_MODEL --out handoffs/task-001-plan.md
# Inspect the plan, then approve or reject it.
python runtime.py task decide-plan --project demo --chat task-001 --id task-001 --decision approve --note "Reviewed current plan artifact"
python runtime.py task begin --project demo --chat task-001 --id task-001
# The executor/caller must log actual actions as they happen.
python runtime.py task log-action --project demo --chat task-001 --id task-001 --description "Ran focused test suite" --status completed --evidence-ref handoffs/test-output.txt
python runtime.py task complete --project demo --chat task-001 --id task-001 --summary "Implemented the approved change" --output-ref handoffs/result.md
python runtime.py task verify --project demo --chat task-001 --id task-001 --overall-status partial --checks-file handoffs/checks.json --notes "See checks for tested and untested criteria."
python runtime.py task export --project demo --chat task-001 --id task-001 --out handoffs/task-001-audit.md
\`\`\`

For each check in \`checks.json\`, provide a non-empty \`criterion\` and a \`status\` of \`pass\`, \`fail\`, \`partial\`, or \`not_tested\`. Passing checks require an \`evidence_refs\` list. Failed, partial, and untested checks require explanatory \`notes\`. A check's evidence reference must point to real material that a reviewer can inspect.

## V2.7 addition retained: Delta-First conformance

After an approved delta has been expanded, `revision verify-output` checks that actual changed Markdown sections stay inside the approved `changed_sections` declaration and compares the output against the pinned base artifact SHA-256.

- A successful scope check marks the output `ready_for_release`.
- Out-of-scope edits, stale bases, unpinned bases, vague section locators, ambiguous headings, or no-op candidates fail closed.
- The verifier checks **textual scope**, not semantic correctness. It cannot prove that prose satisfies the intent of the approved summary.

Machine-checkable `--changed-section` selectors are `heading:Exact / Heading Path`, `preamble`, or `whole-artifact`. A vague description such as `methodology paragraph` is not treated as verified.

See [`DELTA_FIRST_DELIVERY.md`](DELTA_FIRST_DELIVERY.md).

## Existing implemented primitives

- Append-only event ledger with separate provenance, decision authority, inference kind, truth status and source reference.
- Active context as a disposable projection, distinct from full history.
- Branch records with trade-offs; rejected output stays historical and is excluded from active context.
- Pivot-with-reset and chat-identity transition hydration.
- Failed-pattern circuit breaker counting explicit same-strategy rejection, not ordinary edits.
- Source-linked memory candidates, visible accept/edit/reject review, read-only references, separate keep/use decisions and append-only status history.
- Retention/use disposition separated from memory lifecycle and influence permission.
- Project/account scoping and explicit applicability tags.
- Checkpoint export to Markdown and JSON.
- Bounded context packing: protected user content stays verbatim; protected overflow fails closed; optional events are included or omitted whole with IDs for retrieval.
- Delta-first revision proposal, decision, reset/re-plan, base hash pinning, post-expansion textual conformance, and release-readiness checks.
- Strict provider-input allowlist plus optional loopback-only local Ollama adapter.

## Tests

Run from this directory:

```bash
python -m unittest discover -s tests -v
```

**57 unit tests pass**, including an end-to-end CLI call and an interactive multi-turn shell test against a mocked local Ollama endpoint. `runtime.py` compiles. These tests establish local invariants and adapter serialization behavior; they do not establish that the actual Ollama application or a local model is installed or that every AEL mechanism is complete. See [`TEST_REPORT.md`](TEST_REPORT.md).

## Quick start

Record an initial brief:

```bash
python runtime.py record --project memory-prism --chat experiment-001 --type initial_brief --provenance user --authority user_direct --inference-kind user_statement --content "Preserve the original brief and constraints."
```

Assemble a provider-neutral model-input file without calling a model:

```bash
python runtime.py model-input --project memory-prism --chat experiment-001 --current-user-message "Continue from the recovered state" --max-tokens 12000 --out handoff/model-input.json --audit-out handoff/runtime-audit.json
```

For interactive multi-turn local chat (only once Ollama is installed, running locally, and a model is available):

```bash
python ael_chat.py --project memory-prism
```

Or send a single turn from the CLI:

```bash
python runtime.py ollama-chat --project memory-prism --chat experiment-001 --current-user-message "Continue from the recovered state" --model YOUR_LOCAL_MODEL_NAME --out handoff/response.json --audit-out handoff/runtime-audit.json
```

For controlled memory promotion, see [`MEMORY_WORKFLOW.md`](MEMORY_WORKFLOW.md). For revisions and conformance, see [`DELTA_FIRST_DELIVERY.md`](DELTA_FIRST_DELIVERY.md).

## Token-counter limitation

Without a provider/local-model tokenizer, the CLI uses a rough UTF-8 estimate, not a guaranteed token limit for a particular model. The local adapter reserves room for its fixed prompt and the current user message using the same estimate. A model-specific token counter/context length should be added before treating the budget as exact.

## Source documents and implementation records

The original AEL writing remains the authoritative source and is linked, not recopied into this repository. See [`SOURCES.md`](SOURCES.md) for the author's reading order and the original public pages.

- [`DESIGN_ALIGNMENT.md`](DESIGN_ALIGNMENT.md) — mechanism-by-mechanism implementation status.
- [`EVIDENCE_RECONCILIATION.md`](EVIDENCE_RECONCILIATION.md) — how source evidence and engineering inferences are distinguished.
- [`SOURCE_INVENTORY.md`](SOURCE_INVENTORY.md) — provenance and redistribution boundary for material used during development.
- [`MODEL_INPUT_BOUNDARY.md`](MODEL_INPUT_BOUNDARY.md) and [`LOCAL_MODEL_BRIDGE.md`](LOCAL_MODEL_BRIDGE.md) — model-input controls and local adapter.
- [`OWNERSHIP_AND_LICENSE.md`](OWNERSHIP_AND_LICENSE.md) — authorship and licensing boundary.
- [`AUTHORS_NOTE.md`](AUTHORS_NOTE.md) — biological origin of AEL, implementation provenance, verification limits, and zero expectations of maintenance.
- [`CRITICAL_THINKING_PRECOMMITMENT_LOG.md`](CRITICAL_THINKING_PRECOMMITMENT_LOG.md) — precommitted design and chronological implementation record.
- [`dependencies/critical-thinking/DEPENDENCY.json`](dependencies/critical-thinking/DEPENDENCY.json) — pinned critical-thinking skill provenance and licensing.

## Explicit non-goals

No direct integration into ChatGPT or Claude websites; no paid/cloud API integration; no automatic materiality classifier; no automatic semantic-relevance classifier; no production concurrency service; no fully validated locale-tag service; no claim of automatic model-weight learning; no claim that all AEL mechanisms are complete. Locale Tags remain a documented hypothesis and are not overbuilt here.
