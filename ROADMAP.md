# Roadmap

This roadmap tracks implementation work, not changes to the author's AEL framework.

## Scope anchor

AEL is primarily an **accountability mechanism**. It also gives the user more optionality and thinking space by making choices, trade-offs, provenance, uncertainty and prior knowledge more visible. AEL can help examine a workflow; it does not own or manage the workflow.

## Implemented prototype baseline

- [x] Append-only local event history and disposable active-context projection.
- [x] Branch exposure primitives and structural pivot/reset.
- [x] Retention separated from current use/influence.
- [x] Controlled local-to-account memory candidate pipeline with source-linked review and separate use disposition.
- [x] Bounded model-input allowlist and context packing.
- [x] Delta-first proposal/decision/reset and textual conformance checks.
- [x] Loopback-only Ollama adapter and interactive shell, tested against a mock service; no real-model inference claim.
- [x] Multi-user participant identities, actor attribution, repeated participation periods and schema-v3 export.
- [x] CSV participant fixture demonstrating passive presence, distinct actors and re-entry. It is a deterministic attribution fixture, not a workflow manager.
- [x] Canonical active-membership check for explicitly identified human/AI actors and branch proposal pre-write check (PR #32). This enforcement design is now under review; see below.
- [x] Chat-scoped external context intervention records, version hashes and latest-version context projection.

## Current design work — accountability without workflow ownership

- [ ] **Review active-membership rejection gate:** determine whether attempts outside a recorded participation period should be preserved and flagged rather than rejected before an accountability record exists. Do not extend this gate into a general permission system without an explicit design decision.
- [ ] **Complete action receipts:** review supporting AEL operations (memory lifecycle, revision decisions, checkpoints and related actions) for actor, source, object/version, time and recorded authority. The goal is complete evidence, not workflow policing.
- [ ] **Separate authority from membership:** preserve claimed/exercised authority and any host authorisation evidence as distinct facts. Do not build an organisation-wide approver/permission administration system into AEL.
- [ ] **Controlled context reuse:** examine selective reuse of methods and lessons from similar projects without moving whole transcripts or exposing project-sensitive data.
- [ ] **Provenance and applicability:** preserve origin, version/hash, conditions, sensitivity/reuse boundary, selection/review decision and whether/how an item affected new model input.
- [ ] **Host boundary:** authentication, access permissions and protected resource retrieval belong to the host/organisation. AEL records origins, user choices and context actually used.
- [ ] **Review existing mechanisms first:** inspect the memory candidate/review/use pipeline and context intervention records before designing another subsystem.

## Not AEL's job

- End-to-end workflow or project management.
- Organisation-wide identity/access-control or permission administration.
- Automatic propagation of all project context to every related chat.
- Automatic copying of whole conversations or sensitive source documents between projects.

## Not planned without evidence

- Paid API requirement for core local persistence mechanics.
- Automatic learning claims or model-weight changes.
- Silent automatic promotion of local lessons into shared account context.
- New UI/runtime bridge before a real host integration requires it.
- New analytics or dashboard subsystem.

## Historical stabilisation

The V2.8.1 stabilisation work verified the pre-existing ledger, context isolation, pivot/reset, retention/use, delta-first conformance, file-backed source pinning, legacy migration, checkpoint recovery, and loopback-only Ollama mock boundary. The pre-split combined CI run [#388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810) is historical and included Q-Batch tests before repository separation. Current AEL tests run separately from Q-Batch. No real-model inference or blind CT pilot was run.

See [AEL_SCOPE_AND_CONTEXT_REUSE.md](AEL_SCOPE_AND_CONTEXT_REUSE.md), [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md), [NEXT_STEPS.md](NEXT_STEPS.md), and [TEST_REPORT.md](TEST_REPORT.md).
