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

- [x] Repeat the existing test suite from clean checkouts; record exact commits, runtime versions, test counts, and results. Latest code verification: [CI #365](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41794650716), all Python 3.11/3.12/3.13 jobs green; latest documentation verification: [CI #374](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41795220717), all three green.
- [x] Preserve and verify the existing append-only ledger, context isolation, pivot/reset, retention/use, delta-first acceptance, and conformance contracts through the existing AEL tests.
- [x] Preserve and verify file-backed artifact source pinning, hash checks, same-rooted reads, and change/disappearance handling through the existing AEL tests.
- [x] Preserve and verify database reopen, context rehydration, legacy migration, and checkpoint history behaviour. Checkpoint exports use unique checkpoint IDs and contained filename components; regression tests verify historical hashes and output-root containment.
- [x] Keep the loopback-only Ollama boundary and interactive shell covered by mock tests. Do not claim real inference without a captured real-model run.
- [x] Reconcile docs with implemented code and test evidence, including removal of the stale claim that file-backed artifact loading/hash revalidation is unfinished.
- [x] Conduct a focused threat-model and data-handling review. Findings and use restrictions are recorded in SECURITY.md; sensitive-data use remains blocked by missing encryption/access-control/backup/deletion protections, and confidential blind pilot execution remains blocked while raw audit artifacts are published from this public repository.

### Demonstrated defects corrected

- [x] Q-Batch: duplicate submit_plan now stops the runner immediately under the existing one-plan contract; the correction has a deterministic regression test.
- [x] AEL checkpoints: each export has a unique checkpoint ID in its filename, preventing a later checkpoint from overwriting an older snapshot referenced in SQLite.
- [x] AEL checkpoints: project/chat identifiers are URL-encoded in filenames so path separators cannot escape the requested output directory.

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
