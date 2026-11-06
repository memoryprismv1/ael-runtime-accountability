# AEL Context Projection — demo-project / audit-example

- Account: `example-account`
- Hydrated: 2026-11-05T08:00:00+00:00
- Last event sequence: `3`
- Historical events: `3`
- Canonical record: persistent event ledger; this projection is disposable.

## Active context

### #1 · original_query · provenance: user
- Authority: `user_direct` · inference kind: `user_statement` · truth status: `not_applicable`
- Event ID: `EV-SYNTH-0001` · Source ref: `not supplied`

Please produce a small example audit export.

### #3 · assistant_turn · provenance: assistant
- Authority: `none` · inference kind: `generated_artifact` · truth status: `unverified`
- Event ID: `EV-SYNTH-0003` · Source ref: `synthetic-fixture`

This is an example only; do not mistake it for a real AEL session.

## Branch ledger

_No branches recorded._

## Memory influencing this context

_No ratified memory is currently influencing this context._

## Read-only memory references

_No read-only references available._

## Excluded from active context but retained in history

- Event #2 `assistant_turn`: historical_artifact_not_active_by_default — content retained in ledger only (sha256:d887fcf15575)

## Recovery instruction

Rebuild active context from the stable ledger. Do not reintroduce rejected branch artifacts unless the user explicitly asks to reconsider them. Inspect source references before treating an inference or generated artifact as verified fact.
