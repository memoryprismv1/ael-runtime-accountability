# V2.8.1 Test Report — Conformance, Model Boundary, Local Interactive Bridge

**Latest validation:** 57 unit tests passed using Python's standard `unittest`; `runtime.py` and `ael_chat.py` compile. Mock-server end-to-end tests cover the CLI adapter and the interactive chat shell.

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
- Delta approval, base-hash pinning, post-expansion scope conformance and release-readiness checks.
- Mocked Ollama request/response serialization, response parsing, persistence, token-free local connection and separate audit sidecar.

## Real-model status

Ollama was **not installed in the development environment**. No real inference, answer-quality, latency, hardware performance or true model-tokenizer/context-window test was performed. Mock-server tests verify only request/response integration and runtime data boundaries.

## Remaining limits

The conformance checker verifies structural scope, not semantic intent. The offline context counter is approximate. The bridge is not connected to ChatGPT or Claude websites and this is not the complete AEL runtime.


## V2.9 candidate branch — task-level critical-thinking precommitment

**Status at documentation update:** implementation and new tests are on the candidate branch; CI verification is pending.

The new task test module covers skill pin validation, approval gates, case-to-plan hash binding, invalidation of a plan when case notes change, append-only task records, task event mirroring, verification evidence requirements, standalone audit export, and CLI parser exposure. These tests are intended to establish runtime state-transition invariants; they cannot establish that generated reasoning is sound or that execution claims are truthful.

The feature also provides local Ollama generation commands that include the pinned skill text in the model input. Actual generation with a real model has not been verified as part of this code change. There is no general external-action executor in this candidate.

The confirmed test count and any failures must be updated from actual CI results; do not infer a pass from the existence of the tests.
