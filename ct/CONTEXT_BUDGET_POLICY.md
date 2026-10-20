# Model-Facing Context Budget Policy (introduced V2.3; retained in V2.6)

## Purpose

Provide a bounded model-facing context from the active projection without letting context limits silently rewrite the canonical record or give AI verbosity more influence than user constraints.

## Rules implemented

1. **The ledger remains canonical.** The packer consumes the active projection; it does not mutate or summarise historical events.
2. **Protected content stays verbatim.** Active user-originated events, initial briefs, constraints, original queries, corrections and branch-rejection decisions are mandatory. Ratified memories allowed to influence the current context are also mandatory.
3. **Fail closed on protected overflow.** If the mandatory content does not fit the requested budget, the packer raises `ProtectedContextOverflow` and returns no partial context. It reports the required estimate and protected event/memory IDs. It does not silently compress, truncate or drop the user's words.
4. **Optional events are atomic.** The packer selects non-protected active events by deterministic event-type priority and recency. If a complete event does not fit, it omits that whole event and returns an ID-only retrieval hint in the sidecar report. It never cuts an event mid-sentence.
5. **No rejected artifacts.** The packer reads only `active_events` and `memories_influencing_context`; it never copies `excluded_from_active_context`, rejected branch descriptions, or read-only memory claims into model input. Rejection status/usage policy can be present as a control record, but rejected output remains absent.
6. **Old assistant turns are not summarized.** The context projection already removes aged assistant outputs from active input by default. Their full records remain retrievable in the ledger.
7. **Only the context string goes to the model.** The returned report is audit metadata. An adapter must pass `context_text`, not the whole projection, checkpoint JSON, or return object.
8. **Overflow is visible.** Omitted event IDs and reasons are reported outside the model input so a caller can retrieve them explicitly.
9. **Retention is not relevance.** Information can remain stored but have `maybe_later` or `not_pertinent_now` status. Status changes influence projection; they do not delete the underlying record.
10. **Conditional memory needs an applicability signal.** `use_when_relevant` requires a matching explicit relevance tag, or the deliberate `always` tag. `never_try_again` requires an exact matching tag. No automatic semantic relevance classifier is claimed.

## Budget counter limitation

The offline fallback estimates token units from UTF-8 length. This is a portable approximation, not a guaranteed upper bound and not an exact count for any provider/model tokenizer. The optional local Ollama adapter currently uses this fallback estimate; inject the target model's tokenizer/context policy before claiming a hard model-specific token limit. Tests inject a deterministic counter to verify selection and fail-closed behavior without API keys.

## Why no summarization fallback?

The source design differentiates historical availability from active influence. It also explicitly rejects a model summarizing its own aged outputs into a new active claim. For protected user content, silent compression would also risk destroying original provenance and constraint wording. V2.3 therefore prefers explicit overflow to fabricated confidence that nothing important was lost.

## Test coverage

Tests verify verbatim protected content, fail-closed overflow, whole-event omission, zero leakage of rejected branch content, influence/read separation for memories, and context recovery after reopening the SQLite database.

## Remaining work before model integration

- Provide an exact tokenizer/counting function at the eventual model boundary.
- Add a retrieval call that can fetch omitted event IDs only on explicit need, without injecting their content by default.
- Add an end-to-end adapter test proving that only `context_text` enters model input and the audit sidecar is excluded.
