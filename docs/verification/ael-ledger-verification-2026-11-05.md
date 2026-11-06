# AEL ledger verification record — 5 November 2026

**Classification:** implementation/schema and test-verification record; defines the current portable audit-export requirements; **not a live SQLite database backup**.  
**Authoritative source:** [AEL Runtime Accountability](https://github.com/memoryprismv1/ael-runtime-accountability).  
**Code baseline:** `67f83f1e0a8ed704246eef080c8e3950d092c845`.  
**AEL main at archive time:** `844c61c247f604ad0ec4a0b3e8b6f65844849807` (documentation handoff commit; code baseline above is its parent).  
**Clean-checkout CI:** [run #388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810), Python 3.11 / 3.12 / 3.13 all passed.

## What the ledger is

AEL's canonical event ledger is the SQLite `events` table. Each event row records:

- sequence number (`seq`) and unique event ID (`event_id`);
- timestamp (`created_at`);
- account, project and chat scope;
- event type and provenance;
- authority, inference kind and truth status;
- optional source reference, branch ID and strategy key;
- content and JSON metadata.

The runtime's `append_event()` validates the provenance/authority/inference/truth fields, inserts a new row, commits, and returns the inserted event. `scope_events()` reads events for one account/project/chat in sequence order.

The schema installs database triggers that reject updates and deletes to `events`. Related histories also have append-only protections, including memory events, revision events, revision outputs and conformance checks. Branches, memories, memory candidates and checkpoints are stored separately from the event stream.

## What was verified

The 72-test AEL runtime suite passed on Python 3.11, 3.12 and 3.13 in the clean-checkout CI run. Relevant regression coverage includes:

| Test | What it checks |
|---|---|
| `test_history_is_append_only_projection_hides_rejected_branch` | Rejected output remains in history but is excluded from active context. |
| `test_event_ledger_rejects_update_and_delete` | The event ledger rejects direct row updates and deletes. |
| `test_failed_ledger_insert_leaves_no_event_and_connection_can_append` | A simulated rejected insert leaves no phantom row; the same connection can append a later valid event; the valid event remains visible after reopening the database. |
| `test_history_and_context_recover_after_database_reopen` | Historical events survive a fresh connection and context hydration keeps older turns out of the current packed context when requested. |
| `test_legacy_v23_database_migrates_memory_stages_safely` | Legacy memory-stage and usage-status migration. |
| `test_revision_source_path_columns_migrate_existing_databases` | Legacy revision-source path/byte-length columns migrate. |

The failed-insert test uses a temporary SQLite trigger to force a selected insert to fail. It verifies that the failed row is absent, then verifies that a later valid append is durable after database reopen. This is a deterministic regression test of that failure path, not a broad production fault-tolerance guarantee.

The current scorecard PR [#28](https://github.com/memoryprismv1/ael-runtime-accountability/pull/28) does not modify AEL runtime code. Its latest routine CI [#402](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42032791036) also passed on all three Python versions.

## What to preserve from AEL for current auditability

The existing `checkpoint()` export writes two portable files for one account/project/chat scope:

- `checkpoint-<project>-<chat>-<id>.md` — readable by a person.
- `checkpoint-<project>-<chat>-<id>.json` — machine-readable snapshot.

The JSON payload includes the scoped event history split into active and excluded-from-active-context events. It retains event sequence numbers, event IDs, timestamps, event types, provenance, authority, inference kind, truth status, source references, branch IDs, content, and projection status. It also carries the branch/memory context represented by the checkpoint. This makes it useful for ordinary audit questions such as what was recorded, in what order, from which source, and why an item was not active.

**Keep the JSON and Markdown together.** The Markdown is the reading copy; the JSON is needed for reliable inspection of excluded historical content. In the Markdown, excluded event content is intentionally not repeated; only its event identity/status and a short content digest are shown.

For portable integrity checking, calculate SHA-256 for each exported file and save the values in a small adjacent `.sha256` or `SHA256SUMS.txt` file. This means later checks do not depend on reopening the original SQLite database.

Scope limits: a checkpoint is a project/chat projection, not a byte-for-byte export of every auxiliary table. It is enough for the current event-ledger auditability and ordinary handoff/reporting need. It is not intended to support SQL queries, database restoration, or forensic reconstruction of every memory/revision auxiliary-table transition.

## Export status at archive time

The source repository contains the AEL prototype code and its tests. No real session checkpoint export was present in that repository or in the retrieved artifacts. There is no evidence here of a deployed AEL session or of actual user history recorded by AEL.

A paired Markdown/JSON example is stored at [ael-checkpoint-example](ael-checkpoint-example/README.md). Its event names and IDs are fabricated and marked `SYNTHETIC`; it demonstrates the shape of the export only. **It is not a real AEL checkpoint and must not be counted as evidence that AEL has already recorded a session.** This is a boundary on the evidence we currently have, not a request for the user to find or access a separate machine.

## Database investigations — deferred

**No SQLite database backup or database-level investigation is required for the current task.** Revisit only if a specific future question cannot be answered from the exported checkpoint files or the relevant text/JSON audit artifacts.

## Source references

- [Ledger implementation](https://github.com/memoryprismv1/ael-runtime-accountability/blob/main/ael/ledger.py)
- [Database schema and migrations](https://github.com/memoryprismv1/ael-runtime-accountability/blob/main/ael/database.py)
- [Checkpoint implementation](https://github.com/memoryprismv1/ael-runtime-accountability/blob/main/ael/checkpoints.py)
- [Runtime tests](https://github.com/memoryprismv1/ael-runtime-accountability/blob/main/tests/test_runtime.py)
- [Clean-checkout CI #388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810)
