# Multi-user participant workflow fixture

This fixture exercises the AEL schema-v3 participant registry without requiring a real multi-user chat service.

## Files

- `participants.csv` registers six stable identities. Importing the roster does **not** add anyone to a conversation.
- `workflow.csv` drives 16 explicit actions in order: joins, user messages, an assistant branch proposal, a different participant's approval, a manager's departure, and a requester's leave/re-entry.
- `run_fixture.py` imports the roster, executes the steps through the real AEL ledger APIs, and writes a JSON receipt containing the exported ledger and participant history.

The manager joins after the conversation has begun, remains present while a branch is proposed and approved, and never acts. The receipt asserts that the manager is part of the chain during those events despite having no actor-attributed actions. The requester leaves and rejoins under the same participant ID, creating two separate participation periods.

## Run

From the repository root:

```bash
python examples/multi-user-workflow/run_fixture.py
```

By default the SQLite database is temporary and the receipt is written to `handoffs/multi-user-fixture-receipt.json`. To retain the SQLite database as well:

```bash
python examples/multi-user-workflow/run_fixture.py --db handoffs/multi-user-fixture.sqlite3
```

Use `--participants`, `--workflow`, `--account`, `--project`, `--chat` and `--out` to run a different fixture or scope.

## Fixture semantics

- `fixture_key` is only a local CSV alias; it is not the participant's identity.
- The optional `type` column accepts `human` or `agent`. A blank value, or an omitted column, defaults to `human`; agents must be explicitly marked `agent`.
- The importer maps roster `agent` to AEL's internal `ai_agent` participant type. The older `participant_type` column remains accepted for existing fixtures.
- Organisation IDs resolve to `org:<issuer>:<external_id>`.
- The assistant uses an explicit provider ID.
- Roster import is idempotent and validates the entire CSV before the first write.
- Membership exists only after a `join` step and ends only at a `leave` step.
- Membership intervals use `[effective_from_seq, effective_until_seq)`: the start is included and the end is excluded.
- The `actor_key` on a workflow step is distinct from `participant_key`, which is the participant being joined/removed or the speaker.
- `system` is permitted as the actor for initial setup; after that, the coordinator performs membership administration.

This is a deterministic integration test, not a claim that the current Ollama shell or any hosted ChatGPT UI already has native multi-user transport. A real chat adapter can later supply authenticated participant IDs and the same join/leave/actor APIs.
