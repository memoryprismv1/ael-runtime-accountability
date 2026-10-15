# Optional Local Model Bridge (No Paid API Token)

## What it does

`ollama-chat` connects the local AEL runtime to an Ollama model running on the same computer. `ael_chat.py` wraps it as an interactive multi-turn chat, so the user does not need to type a long command for every message. The runtime assembles bounded context from the persistent ledger, sends only the allowlisted context and current request to a loopback API, records the returned answer, and keeps audit metadata separate.

Official Ollama documentation identifies the local API as `http://localhost:11434/api` and supports `POST /api/chat` with `stream: false` for a single JSON response: https://github.com/ollama/ollama/blob/main/docs/api.md and https://github.com/ollama/ollama/blob/main/docs/api/introduction.mdx.

## Requirements

- Python 3.10+ (standard library only; no `pip install` for the bridge).
- Ollama installed and running locally.
- A local model pulled/available in Ollama. No paid API token is needed for local inference.
- Enough system RAM/VRAM for the chosen model. Model suitability and performance depend on the machine; this project does not choose a model without hardware information.

Official Windows download: https://ollama.com/download/windows
Official API introduction and local/cloud distinction: https://github.com/ollama/ollama/blob/main/docs/api/introduction.mdx.

## Lowest-friction launch

1. Install/run Ollama using the official instructions.
2. Make sure at least one model is installed locally. Hardware determines which model is suitable; this package does not guess your PC's capacity.
3. In the extracted folder, double-click `START_AEL_CHAT.bat`, or run:

```bash
python ael_chat.py --project memory-prism
```

The launcher checks the local Ollama service, lists locally installed models, and starts an interactive chat. Each turn is saved to the local SQLite ledger. Type `/new` to create a different chat identity (fresh local context, same account/project), `/status` to view the current scope, or `/quit` to exit.

By default, the database and audit sidecars live outside the versioned package folder: `%LOCALAPPDATA%\AELRuntime` on Windows, or `~/.ael-runtime` on macOS/Linux. This keeps history intact when you replace the program folder with a newer release. Set `AEL_RUNTIME_HOME` to choose another persistent location, or explicitly pass `--db` and `--audit-dir` to override it.

You can also check model availability without prompting a model:

```bash
python runtime.py ollama-status
```

## One-shot CLI

If you prefer a single explicit turn, from the extracted package directory, call:

```bash
python runtime.py ollama-chat \
  --project memory-prism \
  --chat experiment-001 \
  --current-user-message "Continue from the recovered state" \
  --model YOUR_LOCAL_MODEL_NAME \
  --out handoffs/response.json \
  --audit-out handoffs/runtime-audit.json
```

Replace `YOUR_LOCAL_MODEL_NAME` with the exact name from `ollama list`. The default endpoint is `http://127.0.0.1:11434`. The adapter refuses remote hosts and explicitly named Ollama cloud models (names ending in `:cloud`). Keep this command pointed at a locally downloaded model; do not use Ollama cloud models through this bridge.

## What gets sent to the model

Only the bounded active `working_context` and the current user message are passed as content, wrapped in a fixed runtime system instruction. The full event ledger, omitted-content list, rejected drafts, audit sidecar, memory reference IDs, context hashes and diagnostic report are not sent.

The user message and returned assistant content are then recorded to the append-only ledger. Response output and audit file are separate, and the runtime refuses if their paths resolve to the same file.

## Tested vs. not tested

**Tested here:** model-status endpoint with a mock server; configurable stable data-directory resolution; interactive two-turn shell and fresh-chat isolation against a mock local HTTP server; adapter and CLI end-to-end with a mock local HTTP server; allowlist; request shape; response parse; persistence of both turns; separate audit sidecar; no API token; refusal of remote endpoints.

**Not tested here:** actual Ollama inference. There was no `ollama` executable or installed model in this environment. Model quality, performance, actual tokenization/context window, and GPU utilization remain untested.

## Privacy and safety note

Loopback-only endpoints are a safe default for this prototype, not a complete operating-system security guarantee. Keep the local service bound to loopback and do not forward it to a network. Choose a model downloaded to this machine (not an Ollama cloud model). The bridge blocks the documented `:cloud` suffix, though a local Ollama installation itself remains part of the trust boundary. Local model software and downloaded model licenses are separate from the AEL prototype's license; review those independently.
