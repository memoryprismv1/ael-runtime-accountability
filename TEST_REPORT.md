# V2.8.1 Test Report — Conformance, Model Boundary, Local Interactive Bridge

**Repository boundary update (7 November 2026):** the AEL suite contains 82 AEL-only tests: 63 runtime tests, 6 mocked local-bridge tests, 10 multi-user ledger tests and 3 CSV-driven multi-user workflow tests. The multi-user tests cover stable participant IDs, repeated participation periods and half-open boundaries, actor attribution for branch/memory/revision decisions, checkpoint creator/recorder attribution, workflow membership inheritance, rejection of invalid actors before object creation, legacy migration without invented identities, atomic/idempotent roster import, manager presence without action, approval actor separation, and requester re-entry. Pull request CI run [#438](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42373773833) passed all 79 tests on Python 3.11, 3.12 and 3.13. The 3 shared-logger tests and all experiment, method and historical-analysis tests moved to the separate [Q-Batch repository](https://github.com/memoryprismv1/q-batch-of-evidence). The earlier clean-checkout [CI run #388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810) was run before the split and included the Q-Batch suites; it is a historical baseline, not validation of the new AEL-only workflow. The earlier pre-split run #388 remains a historical combined-suite baseline; run #438 validates this AEL-only schema-v3 change.

## V2.8.1 additions

1. `ollama-status` reads the local `/api/tags` inventory without sending a prompt or opening the AEL database.
2. Local-model inventory excludes model tags ending in `:cloud`.
3. `ollama-chat` refuses cloud model tags as well as non-loopback endpoints.
4. Interactive shell performs two turns, stores both user and assistant records in the persistent ledger, and writes per-turn audit files locally.
5. `/new` generates a different chat identity; the next turn hydrates isolated context while keeping account/project scope.
6. Audit metadata, omitted-event records, hashes and event identifiers do not cross the model-input boundary.

## Prior coverage retained

- Declared section changes pass; out-of-scope edits, vague locators, stale bases and no-op changes fail closed.
- Model input allowlist contains only bounded working context and current user message.
- Append-only history, rejected-branch isolation, pivot reset, circuit-breaker behavior, provenance/authority/truth/inference separation, source-linked memory review/promotion, separate retention/use disposition, applicability-tag matching, checkpoint recovery, bounded context and protected overflow.
- Repeated checkpoint exports retain their own files and continue to match the snapshot hashes recorded in SQLite; path-like project/chat identifiers are encoded so exported files remain under the requested output directory.
- Delta approval, base-hash pinning, post-expansion scope conformance and release-readiness checks.
- Mocked Ollama request/response serialization, response parsing, persistence, token-free local connection and separate audit sidecar.
- SQLite failure-injection coverage: a rejected event insert leaves no phantom event, the connection accepts a later valid append, and the persisted event set remains correct after closing and reopening the database.

## Real-model status

Ollama was **not installed in the development environment**. No real inference, answer-quality, latency, hardware performance or true model-tokenizer/context-window test was performed. Mock-server tests verify only request/response integration and runtime data boundaries.

## Remaining limits

The conformance checker verifies structural scope, not semantic intent. The offline context counter is approximate. The bridge is not connected to ChatGPT or Claude websites and this is not the complete AEL runtime.
