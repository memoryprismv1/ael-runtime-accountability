# Runtime and experiment separation

## Shared base

- `ael/database.py` owns the shared SQLite schema, connection setup and backward-compatible database migrations.
- `ael/ledger.py` owns the global, canonical AEL event ledger.
- `testing_logger/logger.py` owns the global testing logger. Its event stream is separate from the AEL ledger. The caller chooses the event vocabulary, call points and call frequency.
- `ael/` contains shared AEL runtime mechanisms: branches, memory, context, sessions, provider transport, checkpoints and revisions.
- `runtime.py` remains a compatibility façade for existing imports and command-line calls.

## Experiments

Experiments remain under `experiments/`. They can call the global testing logger once or many times at whatever stages their protocol requires. Experiment-specific schemas, scoring, paired-run orchestration, task definitions, dependency pins and interpretation remain inside the experiment.

The CT adapter in `experiments/ct_ab/logger.py` preserves the existing `RunLogger` API while delegating to the shared logger engine.

## Non-negotiable boundary

The AEL ledger records AEL runtime activity. The testing logger records experimental observations about AI responses and their test conditions. Testing records do not automatically become AEL events, and experiments do not get their own copies of the AEL base.

## Compatibility and migration

The initial modularisation preserves the old `runtime.py` import surface. Existing database tables and migrations remain in the shared database module. Existing tests and Q-Batch contract tests are retained as regression coverage.
