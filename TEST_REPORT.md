# AEL Runtime Test Report — V2.8.1 prototype and multi-user/context extensions

**Latest AEL-only CI (7 November 2026):** PR [#32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32), workflow run [#445](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42377856668), passed **85 tests on each of Python 3.11, 3.12 and 3.13**. The run includes compilation of the runtime and tests before executing the full unittest suite. PR #32 was squash-merged as commit `301fb4bec68829460509851d83d2e225a859faad`. The merged code adds canonical active-membership enforcement, pre-write branch-proposal validation, versioned external context intervention events, and tests that model input changes without rewriting the visible message transcript.

**Prior merged baseline:** PR [#31](https://github.com/memoryprismv1/ael-runtime-accountability/pull/31), workflow run [#442](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42375531422), passed 82 tests on Python 3.11/3.12/3.13. PR [#30](https://github.com/memoryprismv1/ael-runtime-accountability/pull/30) introduced the schema-v3 participant registry and actor attribution. The 3 shared-logger tests and experiment/method/historical-analysis tests are in the separate [Q-Batch repository](https://github.com/memoryprismv1/q-batch-of-evidence), not this AEL suite.

## New participant enforcement coverage

- Identified human/AI actor is rejected before joining, accepted within an active period, and rejected after leaving.
- A rejected pre-join branch proposal leaves no branch row behind.
- Existing half-open join/leave and re-entry semantics remain covered.
- Membership remains distinct from approval permission; no role/capability authorization matrix is implemented yet.

## New external context intervention coverage

- A context intervention changes the provider-facing working context and its SHA-256 audit hash while the user/assistant message transcript remains unchanged.
- Only the latest intervention for each resource ID is injected; prior versions remain in immutable history.
- An unjoined actor cannot change context.
- A stale expected previous hash is rejected.
- The intervention content and resource/version/source/actor metadata remain separate from the sidecar data sent to the model.

## Prior coverage retained

- Declared section changes pass; out-of-scope edits, vague locators, stale bases and no-op changes fail closed.
- Model input allowlist contains only bounded working context and current user message.
- Append-only history, rejected-branch isolation, pivot reset, circuit-breaker behavior, provenance/authority/truth/inference separation, source-linked memory review/promotion, separate retention/use disposition, applicability-tag matching, checkpoint recovery, bounded context and protected overflow.
- Repeated checkpoint exports retain their own files and continue to match the snapshot hashes recorded in SQLite; path-like project/chat identifiers are encoded so exported files remain under the requested output directory.
- Delta approval, base-hash pinning, post-expansion scope conformance and release-readiness checks.
- Mocked Ollama request/response serialization, response parsing, persistence, token-free local connection and separate audit sidecar.
- SQLite failure-injection coverage: a rejected event insert leaves no phantom event, the connection accepts a later valid append, and the persisted event set remains correct after closing and reopening the database.

## Real-model status

Ollama was **not installed in the development environment**. No real inference, answer-quality, latency, hardware performance or true model-tokenizer/context-window test was performed. Mock-server and fixture tests verify runtime invariants and request/response integration, not actual hosted ChatGPT behaviour or live shared-project context delivery.

## Remaining limits

The canonical event append boundary enforces membership for explicitly identified human/AI actors; direct supporting-table paths such as memory lifecycle events and checkpoint creation still need an enforcement pass. Membership is not approval authority. External context intervention support is currently chat-scoped and requires a host adapter to supply trusted actor identity and source references. The conformance checker verifies structural scope, not semantic intent. The offline context counter is approximate. This is not the complete AEL runtime.
