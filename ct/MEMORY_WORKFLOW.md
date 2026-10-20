# Memory Workflow — V2.5

This walkthrough shows the local-candidate → shared read-only reference → use-disposition path. It is an offline CLI workflow; no model provider or API token is involved.

## 1. Record the source event

Use the actual correction, decision, observation, or other source event. The command prints a sequence number (`seq`). Do not invent a source reference.

```bash
python runtime.py --db data/demo.sqlite3 --account default record \
  --project example --chat chat-1 \
  --type user_correction --provenance user --authority user_direct \
  --inference-kind user_statement \
  --content "Retain the alternative interpretation; it is not pertinent to this task."
```

## 2. Propose a local candidate

Use the `seq` returned by the previous command. The returned `memory_id` is the ID for the following commands.

```bash
python runtime.py --db data/demo.sqlite3 --account default memory propose \
  --scope account --tag writing \
  --claim "Retain alternatives and control their use by task relevance." \
  --source-event-seq 1
```

Replace `1` with the real source event sequence. The candidate remains local and has no influence permission.

## 3. Review the claim

If the claim is exactly right, accept it without passing a changed `--claim`:

```bash
python runtime.py --db data/demo.sqlite3 --account default memory review \
  --id MEM-REPLACE-WITH-RETURNED-ID --decision accept \
  --note "Accepted as a concise, source-linked claim."
```

If you are changing the wording, use `--decision edit` and provide the revised `--claim`. If you reject it, the candidate stays recorded locally; it is not shared and is not deleted. A rejected local candidate can be reopened with `memory reopen --id MEM-...`.

Acceptance creates a **shared read-only reference**, not an authoritative instruction. There is another distinct decision before it can influence runtime context.

## 4. Set how the information may be used

```bash
python runtime.py --db data/demo.sqlite3 --account default memory resolve \
  --id MEM-REPLACE-WITH-RETURNED-ID --decision not_pertinent_now \
  --note "Keep it, but do not use it in the current work."
```

Available choices:

- `use` — useful when relevant; it still requires the exact applicability tag, unless the tag was deliberately set to `always`.
- `avoid` — do not repeat this strategy when its exact applicability tag matches.
- `later` — retain for later; do not inject automatically now.
- `not_pertinent_now` — retain, but do not inject automatically into the current context.

These change use policy, not historical retention. A change is recorded as an event. There is no user-facing delete/discard action in this workflow.

## 5. Inspect memory and test a context projection

```bash
python runtime.py --db data/demo.sqlite3 --account default memory list --include-local
python runtime.py --db data/demo.sqlite3 --account default model-context \
  --project example --chat chat-1 --max-tokens 12000 --relevance-tags writing
```

The `model-context` output includes `context_text` and a report. Only `context_text` is intended for a future model adapter. Do not send the full database, historical ledger, checkpoint JSON, or report sidecar to a model; those can contain material excluded from the active projection.

## Important limitation

The prototype does not infer semantic relevance by itself. The runtime caller supplies relevance tags. The default offline token estimate is approximate, not provider-tokenizer exact. No model connection is implied by this workflow.
