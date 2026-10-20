> Historical delta note for the V2.7 baseline. Current status and validation counts are in `DESIGN_ALIGNMENT.md` and `TEST_REPORT.md`.

# Version Delta Audit — V2.6 → V2.8

## V2.7 — Conformance + model-input boundary

- Added post-expansion Markdown scope verification against the pinned base artifact.
- Failed/unverifiable conformance cannot be released by default and triggers a fresh planning state.
- Added an allowlisted model-input object with a separate audit sidecar.

## V2.8 — Optional local Ollama bridge

- Added a loopback-only Ollama `/api/chat` adapter that accepts only the bounded context and current user message.
- User request and model response are recorded in append-only history.
- Response and audit outputs are always separate; same resolved path fails closed.
- Added a CLI end-to-end test against a mocked local server; 51 unit tests now pass, including a CLI end-to-end mock-server test and output-path collision protection.
- No actual local model inference was run because Ollama was not installed in the development environment.

## Limitations not to overclaim

- The delta conformance check is structural/textual, not semantic.
- Context length uses a rough estimate rather than a model-specific tokenizer.
- The adapter can call an installed local Ollama model, but does not connect to ChatGPT/Claude web chats and doesn't alter model weights.
- Cross-session memory service, automated lesson extraction and production concurrency remain unfinished.
