# AEL runtime boundary

## AEL owns

- `ael/database.py` owns the shared SQLite schema, connection setup and backward-compatible database migrations.
- `ael/ledger.py` owns the global, canonical AEL event ledger.
- `ael/` contains AEL runtime mechanisms: branches, memory, context, sessions, provider transport, checkpoints and revisions.
- `runtime.py` remains a compatibility façade for existing imports and command-line calls.
- `tests/` contains AEL runtime and mocked local-bridge tests.

## Q-Batch is separate

[Q-Batch of Evidence](https://github.com/memoryprismv1/q-batch-of-evidence) owns the shared testing logger, event schemas, experiment runners, capture/validation code, scoring, methodology demonstrations, historical analysis and Q-Batch CI.

A test may exercise AEL and emit two receipt streams:

- The AEL ledger records AEL runtime activity and decision authority.
- Q-Batch records experimental execution, conditions, observed model/tool activity and evidence.

These are distinct records. Q-Batch logs do not become AEL events, and AEL ledger events do not replace Q-Batch run records.

## Non-negotiable boundary

AEL is the system under examination. Q-Batch is the test and evidence machinery. Keep each project's implementation and tests in its own repository. Do not duplicate Q-Batch logger code in AEL or AEL ledger code in Q-Batch.

## Compatibility

The existing `runtime.py` import surface and AEL database schema/migrations remain within this repository. Q-Batch may consume AEL-generated receipts as test evidence but does not own or modify the canonical AEL ledger.
