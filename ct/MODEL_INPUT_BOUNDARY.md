# Provider-Neutral Model-Input Boundary

**Status:** Allowlist enforced; local Ollama adapter implemented and mock-tested. No live Ollama/model inference was run in the development environment.

## Why separate the request from the audit

The active context packer returns model-facing text and diagnostic metadata. Sending that whole object to a model would defeat the separation: the model could receive omitted-event references, memory IDs, hashes, or information used only by the runtime to audit its behavior.

`build_model_input()` returns two distinct objects.

### Model input — the only context object the adapter accepts

```json
{
  "working_context": "<bounded active projection only>",
  "current_user_message": "<current user request>"
}
```

### Audit sidecar — runtime-only

Contains account/project/chat IDs, ledger position, context hash, included/protected/omitted event IDs, memory IDs, budget/counter information, and policy notes. Omitted-event entries contain IDs and retrieval hints, not omitted content. The audit sidecar is written separately and never passed to `ollama_chat()`.

## Adapter behavior

`ollama-chat` constructs Ollama's non-streaming `POST /api/chat` request from the two allowed fields, plus a fixed runtime system prompt and the selected local model name. It refuses remote endpoint hosts by default. It does not accept an API token, and does not send to a cloud URL.

The adapter uses `http://127.0.0.1:11434` by default and requires a bare loopback origin. Each successful call records the user request and assistant response to the ledger, writes the response result, and writes audit metadata to a distinct path. Both model-input/audit and response/audit paths are required to resolve to different files.

## CLI

Provider-neutral input only:

```bash
python runtime.py --db data/ael.sqlite3 model-input --project memory-prism --chat experiment-001 --current-user-message "Continue from the recovered state" --out handoff/model-input.json --audit-out handoff/runtime-audit.json
```

Optional local inference, if Ollama is installed and running with a local model available:

```bash
python runtime.py --db data/ael.sqlite3 ollama-chat --project memory-prism --chat experiment-001 --current-user-message "Continue from the recovered state" --model YOUR_LOCAL_MODEL_NAME --out handoff/response.json --audit-out handoff/runtime-audit.json
```

The second command needs no paid API key. See [`LOCAL_MODEL_BRIDGE.md`](LOCAL_MODEL_BRIDGE.md).

## Boundary tests

- Model-input keys are an allowlist: exactly `working_context` and `current_user_message`.
- Rejected branch artifacts and aged assistant turns excluded by policy are absent from active working context.
- Unratified/read-only memory claims are not injected.
- Event omission data, memory IDs, token diagnostics, and audit metadata remain outside the model input.
- Adapter refuses non-loopback endpoints, malformed inputs and malformed responses.
- A mocked HTTP server verified the full CLI path: context → local adapter request → assistant response persisted to the ledger; the audit file remains separate and no token is used.
- Model/input and audit destinations resolving to the same path are rejected before writing or model calls.

## Limits

The mock test establishes request and response handling, not real model behavior. Ollama was not installed in this development environment; no real local model was called. The fallback token counter is a rough estimate, not a model-specific tokenizer. This is not a ChatGPT/Claude website integration and does not connect to cloud endpoints.
