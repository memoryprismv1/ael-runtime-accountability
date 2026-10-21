# AEL Runtime — Next Steps / Handoff

**Current build:** V2.8.1 — source-reconciled local prototype with retention/use policy, memory-promotion stages, delta-first delivery and conformance checking, bounded model context, an optional loopback-only Ollama adapter, and an interactive local chat shell.
**Latest validation:** 57 unit tests and mocked-model end-to-end tests passed.
**Ownership:** AEL and the source architecture belong to the user. This is an implementation handoff, not a new AEL specification.

## What V2.8.1 added

- Added `ollama-status` to check a loopback Ollama service and enumerate model names without sending a prompt or opening the AEL database.
- Added `ael_chat.py` and `START_AEL_CHAT.bat` for interactive multi-turn use; turns persist in the same append-only ledger. `/new` changes chat identity and isolates the next local context.
- Explicitly excludes model names ending in `:cloud`; this bridge is local-only and requires no paid API token.
- Added tests for model inventory, unsafe-host refusal, cloud-model refusal, interactive persistence, local audit sidecars, and new-chat isolation.
- Cleaned conflicting older descriptions about the model adapter's status.

## Completed in the current experiment branch

- **Path-rooted artifact integration:** file-backed delta-first commands load UTF-8 source artifacts beneath an explicit workspace root, compute the base SHA-256 at proposal time, re-read the same source before expansion and verification, reject changed bases and path escapes, and record source/output provenance in immutable events and conformance reports. This closes the caller-supplied-content/hash gap for the file-backed workflow; lower-level APIs remain for compatibility.

## What remains most valuable

1. **Real model run:** the package needs Ollama and a suitable locally downloaded model on the target machine. This environment has no Ollama executable, so only the API contract and shell loop were tested against a mock.
2. **Semantic conformance check:** structural scope verification catches out-of-scope edits, but a domain test or independent check is needed to verify that output fulfills the approved delta.
3. **Automatic lesson extraction:** turn recorded corrections/outcomes into sourced candidate lessons and regression cases. Retain data, separate retention from use, and require explicit review/promotion.
4. **Memory walk-back automation:** define and test time-based decay/reactivation when useful; keep it small and avoid forced maintenance forms.
5. **UI/runtime bridge:** improve the local shell into a UI only if a real use case warrants it; it should not expose audit-only data to the model.

## Do not do

- Do not describe this as the complete AEL runtime.
- Do not claim a real local-model inference was run in this environment.
- Do not introduce a paid API requirement merely to test local persistence or control-flow mechanics.
- Do not treat source essays or the Evidence Pack as subordinate to implementation convenience.
- Do not infer source truth from model self-report.
- Do not delete retained history because a record is currently irrelevant.
- Do not expand a full artifact before the exact delta is explicitly accepted.
- Do not mark a candidate release-ready until structural conformance passes.
