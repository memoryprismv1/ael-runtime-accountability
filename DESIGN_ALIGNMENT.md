# AEL Runtime — Design Alignment and Implementation Status

**Current status:** V2.8.1 local prototype. The interactive shell uses a stable per-user data directory outside the versioned package folder by default. It implements and tests selected runtime primitives; it is not a complete AEL runtime or production specification.

**Controlling sources:** the user's five-page AEL reading sequence, `AEL Runtime Accountability — V1`, the technical Design Notes, and the V1 Evidence Pack. Those sources remain authoritative.

## Design constraints preserved

1. Legibility, not self-trust: make decisions and artifacts inspectable; model self-report is not the accountability mechanism.
2. Materiality is a gate: branching is not a blanket ritual. Clarify cheaply when appropriate; offer single-path, branch, or recommend modes and allow overrides. Automatic classification remains unimplemented.
3. Branches expose material trade-offs before expensive execution.
4. Reset is structural: discard the active local context object and rehydrate; do not merely tell the model to ignore rejected content.
5. One active chat maps to one local context; chat identity change destroys and rebuilds it.
6. History is append-only. Active context is a disposable projection.
7. User rejection reasons remain visible as control signals while rejected generated artifacts remain out of active context.
8. Provenance, decision authority, truth status and inference kind are separate dimensions.
9. Retention is separate from relevance and authority. Old or rejected data may remain retrievable without influencing present work.
10. Local memory lessons must pass visible review before becoming shared references, and require a separate use-policy decision before influence.
11. Project context remains scoped; no silent promotion into general account context.
12. Delta-first approval binds to an immutable proposal hash. Rejection resets from stable state; expansion requires acceptance.
13. Post-expansion verification compares actual changed sections with the accepted scope and checks the pinned base hash.
14. Model input is allowlisted and separate from the audit sidecar. The optional local adapter consumes only that model input envelope.
15. Local model calls default to a loopback-only Ollama endpoint. No API token is accepted and remote hosts are refused.
16. No automatic global learning or claims that a live model instance changes model weights.

## Mechanism status

| Source mechanism | V2.8 status | Remaining gap |
|---|---|---|
| 0 — Materiality Gate | Interaction primitive implemented: single-path, clarify, branch, recommend and override choices are logged. | Automatic cheap pre-filter/classifier and interactive UI. |
| 1 — Branch Exposure | Branch records carry real trade-offs. | Automatic branch generation and UI. |
| 2 — Pivot-with-Reset | Local context destroyed and rehydrated; rejected branch output excluded from active context. | Live deployment boundary/integration tests beyond local adapter. |
| 3 — Failed-Pattern Circuit Breaker | Explicit same-strategy rejection counter; normal edits don't count. | UI and caller that forces strategic diversification. |
| 4 — Account Context | Source-linked candidate, visible review, shared read-only reference and separate keep/use decision. | Cross-process service/concurrency and opt-in UI. |
| 5 — Locale Tags | Deferred as an explicit hypothesis. | Only revisit when a real case warrants it. |
| 6 — Tag Weight / Walk-back | Active/dormant/reversed states and read/influence split. | Time-based decay and confirming-use reactivation. |
| 7 — Locale Conflict = Branch | Representable as a manual branch. | Automatic conflict detection. |
| 8 — Context Pollution Control | Asymmetric assistant-turn handling, provenance fields, memory stages and usage rules, rejected-content isolation, model-input allowlist and local adapter. | Live shared-reference service, production concurrency and real-Ollama run on target hardware. |
| 9 — Project Context | Memory scope is project-contained. | Full project frame/tag/branch service. |
| 10 — Delta-First Delivery | Immutable proposal, changed-scope preview, explicit accept/reject, reset/replan, pinned base hash, post-expansion textual-scope conformance record, fail-closed release status. | UI, automatic delta generation, semantic conformance verification and integration with real artifact editor. |
| 11 — Cheap Pre-Filter | Not implemented. | Empirical comparison on false positives/negatives before choosing a method. |
| Context budget | Protected user content is verbatim; protected overflow fails closed; optional events are whole-record inclusion/omission. | Exact model tokenizer and context-window setting for each chosen model. |
| Model connection | Loopback-only Ollama adapter plus interactive multi-turn shell; model-status check; uses allowlisted input, records request/response, excludes `:cloud` models, refuses remote hosts, no API token. | Ollama and a local model were not installed here, so actual inference/performance remains untested. No ChatGPT/Claude web integration. |

## Candidate extension — Task-level Critical Thinking + AEL precommitment

**Status:** Implemented on the V2.9 candidate feature branch; test validation is tracked separately in \`TEST_REPORT.md\`.

The candidate task lifecycle is implemented in \`ael_task_precommitment.py\` and uses separate task tables in the existing SQLite database, while mirroring task lifecycle events into the existing append-only event ledger. It does not overload the document-revision state machine.

- Case notes and implementation plans are immutable, versioned artifacts with SHA-256 hashes.
- User decisions are append-only records bound to the exact artifact ID and hash.
- An implementation plan is bound to the exact approved case-note hash.
- Replacing case notes clears the current plan; old artifacts and decisions remain historical.
- Execution start fails closed unless the current case and current plan both have approved decisions and the plan's case hash matches.
- Each task stores a dependency identity for the pinned critical-thinking skill; generation uses that bundled source as guidance.
- The export packages the task request, skill provenance, artifacts and hashes, approvals/rejections, action records, verification checks, and chronology.

**Boundary:** this task protocol enforces state and records inside the runtime. The initial local Ollama integration generates case notes and plans but does not provide a general tool/action executor. Action records supplied by a caller are not independent proof that the described action occurred. The final report explicitly distinguishes auditability from semantic truth.

## Mechanism 10: verification boundary

After expansion, `revision verify-output` loads the immutable candidate, checks that its content hash is intact, verifies the supplied base file against the accepted proposal's pinned SHA-256, then compares actual changed Markdown blocks against the declared section scope.

- `pass`: output can be exported through the normal CLI as ready for release.
- `fail` or `unverifiable`: output remains historical but is not release-ready; the proposal enters `rejected_reset`, with the failed scope check available as a correction signal for a fresh delta.
- `heading:Full / Heading Path`, `preamble`, and `whole-artifact` are the machine-checkable selectors. Vague descriptions fail closed.

This catches out-of-scope textual changes; it cannot establish that the new text semantically fulfills the proposal. That needs domain-specific checks, tests, or human evaluation.

## Validation status

**57 unit tests pass**, `runtime.py` compiles, and the end-to-end CLI + interactive shell bridge tests passed against a mocked local Ollama API. This confirms request construction, ledger writes, response/audit separation and the no-token boundary under the tested conditions. It does **not** prove real local model inference or that every mechanism in AEL is complete. See `TEST_REPORT.md`.
