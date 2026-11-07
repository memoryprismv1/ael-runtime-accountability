# Roadmap

This roadmap tracks implementation work, not changes to the author's AEL framework.

## Implemented prototype baseline

- [x] Append-only local event history and disposable active-context projection.
- [x] Branch exposure primitives and structural pivot/reset.
- [x] Retention separated from current use/influence.
- [x] Controlled local-to-account memory candidate pipeline.
- [x] Bounded model-input allowlist and context packing.
- [x] Delta-first proposal/decision/reset and textual conformance checks.
- [x] Loopback-only Ollama adapter and interactive shell, tested against a mock service; no real-model inference claim.
- [x] Multi-user participant registry, stable IDs, repeated participation periods and schema-v3 export.
- [x] CSV roster import and 16-step workflow fixture proving presence without action, distinct proposer/approver attribution, and leave/re-entry.
- [x] Active-membership enforcement for explicitly identified human/AI actors at canonical event append.
- [x] Branch proposal validates membership before writing branch state.
- [x] Chat-scoped external context interventions with actor/authority/source attribution, content hashes and latest-version projection.
- [x] Model-input change test while preserving the visible user/assistant message transcript.
- [x] Chronological implementation log and current handoff.

## Current phase — close the remaining boundaries

- [ ] Extend membership enforcement to direct supporting-table write paths, particularly memory lifecycle actions and checkpoint creation.
- [ ] Define approval capabilities/delegation independently from participant membership and role labels.
- [ ] Decide cross-chat/project-wide context-resource semantics before implementing propagation.
- [ ] Connect to a real host participant/resource source when available; correlate intervention records with the actual model-input hash.

## Not planned without evidence

- Paid API requirement for core local persistence mechanics.
- Automatic learning claims or model-weight changes.
- Silent automatic promotion of local lessons into shared account context.
- A new UI/runtime bridge before a real host integration requires it.
- A new analytics or dashboard subsystem.

## Historical stabilisation

The V2.8.1 stabilisation work verified the pre-existing ledger, context isolation, pivot/reset, retention/use, delta-first conformance, file-backed source pinning, legacy migration, checkpoint recovery, and the loopback-only Ollama mock boundary. The pre-split combined CI run [#388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810) is historical and included Q-Batch tests before repository separation. Current AEL tests run separately from Q-Batch. No real-model inference or blind CT pilot was run.

See [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md), [NEXT_STEPS.md](NEXT_STEPS.md), and [TEST_REPORT.md](TEST_REPORT.md) for the current engineering record.
