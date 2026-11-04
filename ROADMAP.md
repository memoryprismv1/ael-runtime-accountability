# Roadmap

This roadmap tracks implementation work, not changes to the author's AEL framework.

## Current prototype baseline

- [x] Append-only local event history and disposable active-context projection.
- [x] Branch exposure primitives and structural pivot/reset.
- [x] Retention separated from current use/influence.
- [x] Controlled local-to-account memory candidate pipeline.
- [x] Bounded model-input allowlist and context packing.
- [x] Delta-first proposal/decision/reset and textual conformance checks.
- [x] Loopback-only Ollama adapter and interactive shell, tested against a mock service.
- [x] Automated tests in GitHub Actions workflow.
- [x] Workspace-rooted file-backed artifact reader that pins and hashes source bytes and revalidates them during expansion/verification.

## Current phase: stabilisation only

No new features are in scope unless a minimal change is required to repair a demonstrated defect in existing behaviour.

1. Repeat the existing test suite from clean checkouts; record exact commits, commands, runtime versions, and test results.
2. Preserve and verify the existing append-only ledger, context isolation, pivot/reset, retention/use, delta-first acceptance, and conformance contracts.
3. Preserve and verify file-backed artifact source pinning, hash checks, same-rooted reads, and change/disappearance handling.
4. Preserve and verify database reopen, context rehydration, legacy migration, and checkpoint history behaviour. Checkpoint exports now use unique checkpoint IDs and contained filename components; regression tests verify historical hashes and output-root containment.
5. Keep the loopback-only Ollama boundary and interactive shell covered by mock tests. Do not claim real inference without a captured real-model run.
6. Reconcile docs with implemented code and test evidence.
7. Conduct a focused threat-model and data-handling review before recommending use with sensitive content.

## Deferred — not active work

These items would add or expand capabilities and must not be started during the current stabilisation phase:

- independent semantic conformance engine beyond existing checks;
- memory walk-back decay/reactivation automation;
- automatic lesson extraction or automatic promotion;
- new UI or runtime bridge;
- new storage, analytics, or dashboard components.

## Not planned without evidence

- Paid API requirement for core local persistence mechanics.
- Automatic learning claims or model-weight changes.
- Silent automatic promotion of local lessons into shared account context.
- Automatic locale clustering beyond the author's documented scope.
- A full UI unless a demonstrated use case warrants it.

A stable, reproducible implementation of the current baseline is the deliverable. Do not expand the feature set to make the roadmap look active.
