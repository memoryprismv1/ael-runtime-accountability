# V2.8.1 Test Report — Conformance, Model Boundary, Local Interactive Bridge

**Repository boundary update (6 November 2026):** the AEL suite now contains 69 AEL-only tests: 63 runtime tests and 6 mocked local-bridge tests. The 3 shared-logger tests and all experiment, method and historical-analysis tests moved to the separate [Q-Batch repository](https://github.com/memoryprismv1/q-batch-of-evidence). The earlier clean-checkout [CI run #388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810) was run before the split and included the Q-Batch suites; it is a historical baseline, not validation of the new AEL-only workflow. The first post-split CI run will establish the new baseline.

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
