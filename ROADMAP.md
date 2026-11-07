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
- [x] CSV participant roster import and 16-step simulated workflow proving presence without action, separate proposer/approver identities, and leave/re-entry.
- [x] Canonical event active-membership enforcement for explicitly identified human/AI actors; reserved fallback and system/service actor paths remain explicit exceptions.
- [x] Branch proposal checks actor membership before writing branch state.
- [x] Chat-scoped external context intervention records with content/version hashes, latest-version context projection, and audit sidecar metadata.

## Current phase — validate the boundaries

- [ ] Confirm the current branch's three-version CI run and merge only after all tests pass.
- [ ] Extend active-membership enforcement to supporting-table write paths: memory lifecycle, revision lifecycle and checkpoint creation.
- [ ] Separate membership from action permission; specify and test approval capabilities/delegation rather than assuming that an `approver` label is sufficient.
- [ ] Test multiple external context resources, stale writers and the actual host-to-model correlation path.
- [ ] Decide what a project-wide context source means across multiple chats before implementing cross-chat propagation.

## Not planned without evidence

- Paid API requirement for core local persistence mechanics.
- Automatic learning claims or model-weight changes.
- Silent automatic promotion of local lessons into shared account context.
- A new UI/runtime bridge before a real host integration requires it.
- A new analytics or dashboard subsystem.

## Historical stabilisation record — 5 November 2026

The prior V2.8.1 stabilisation work verified the existing ledger, context isolation, pivot/reset, retention/use, delta-first conformance, file-backed source pinning, legacy migration, checkpoint recovery, and the loopback-only Ollama mock boundary. The pre-split combined CI run [#388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810) is historical and included Q-Batch tests before repository separation. The current AEL-only validation is run separately from Q-Batch. A real-model inference or blind CT pilot was not run. See [NEXT_STEPS.md](NEXT_STEPS.md) and [TEST_REPORT.md](TEST_REPORT.md).
