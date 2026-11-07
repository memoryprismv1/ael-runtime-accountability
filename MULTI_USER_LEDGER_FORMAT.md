# Multi-user AEL ledger format — schema version 3

This document describes the participant and actor-attribution extension to the canonical AEL ledger. It extends the existing append-only event history; it does not replace AEL's provenance, authority, inference-kind, truth-status, branch, memory, or revision mechanisms.

## Core distinction

- **Participant:** an identity included in a conversation or workflow chain for a defined period. A participant does not need to perform an action to remain part of the chain.
- **Actor:** the participant who performed a particular action recorded by an event.
- **Authority:** the kind of permission or authority under which the action was taken. This remains separate from identity.
- **Recorder:** the system/service that persisted the record.
- **Represented principal:** the person or entity on whose behalf an actor acted, when applicable.

A manager who was present in a workflow but did not approve, reject, or execute a step remains in the participant history. Membership alone does not prove that the manager read a particular message, was notified, or understood it; those require separate evidence.

## Participant registry

The database holds one account-scoped `participants` row per stable identity. The exported ledger snapshot includes a `participants` array. Events reference IDs instead of repeating names.

Example:

```json
{
  "participant_id": "org:example-company:user-123",
  "participant_type": "human",
  "identity_source": "organisation",
  "issuer": "example-company",
  "external_id": "user-123",
  "display_name": "Morgan Lee",
  "metadata": {},
  "participation_periods": []
}
```

Identity rules:

- Organisation identities are namespaced as `org:<issuer>:<external_id>`.
- When an organisation identity is unavailable, AEL can generate a stable UUID-based participant ID.
- AI agents, tools/services, and system processes are participants too.
- Display names are descriptive, not identity keys. Matching names never merges identities.
- Explicit actor IDs must be registered before use. A misspelled ID is rejected rather than silently added as a new person.

Python API:

```python
participant = register_participant(
    con,
    account="acct-1",
    identity_source="organisation",
    issuer="example-company",
    external_id="user-123",
    participant_type="human",
    display_name="Morgan Lee",
)
participant_id = participant["participant_id"]
```

## Participation periods

Each participant object may contain multiple `participation_periods`. Each period is scoped to an account, project, chat and, optionally, a workflow. A person can leave and rejoin; each return creates a new period. A role change is represented by closing the old period and starting a new one with the new role.

```json
{
  "role": "manager",
  "workflow_id": "approval-flow-7",
  "started_by_event_id": "EV-join-1",
  "effective_from_seq": 43,
  "ended_by_event_id": "EV-leave-1",
  "effective_until_seq": 82
}
```

Boundaries use a half-open interval:

`[effective_from_seq, effective_until_seq)`

- The start sequence is included.
- The end sequence is excluded.
- A join event is recorded first; membership begins at the next event sequence.
- A leave event is recorded while the participant is still in the period; membership ends at the next event sequence.
- A null end means the period is currently open.
- Re-entry never reopens or rewrites the old period.

This makes it possible to reconstruct who was a participant at a particular event sequence. For a workflow-specific lookup, `participants_at_sequence(..., workflow_id="...")` includes both chat-wide participants and participants added specifically to that workflow.

Python API:

```python
join_participant(
    con,
    account="acct-1",
    project="project-a",
    chat="chat-a",
    participant_id=participant_id,
    role="manager",
    actor_id=adder_participant_id,
    workflow_id="approval-flow-7",
)

leave_participant(
    con,
    account="acct-1",
    project="project-a",
    chat="chat-a",
    participant_id=participant_id,
    actor_id=remover_participant_id,
    workflow_id="approval-flow-7",
)
```

## Event attribution

New canonical `events` rows carry:

| Field | Meaning |
|---|---|
| `actor_id` | Who performed the action |
| `on_behalf_of_id` | Whose authority/interest the actor represented, if applicable |
| `recorded_by_id` | Which system persisted the record |

These supplement, and do not replace:

- `provenance`: user, assistant, external, or system
- `authority`: none, user direct, user-ratified recommendation, delegated execution, or system process
- `inference_kind`
- `truth_status`

The same attribution fields are present on memory and revision lifecycle events. Their high-level APIs accept an explicit `actor_id` for decisions such as branch selection, memory review/disposition, and revision approval/rejection.

Example event:

```json
{
  "event_type": "branch.selected",
  "provenance": "user",
  "authority": "user_direct",
  "actor_id": "org:example-company:user-456",
  "on_behalf_of_id": null,
  "recorded_by_id": "ael:system:runtime",
  "branch_id": "branch-7"
}
```

## Export

`scope_ledger(con, account, project, chat)` returns a schema-version-3 snapshot containing:

- `participants`: de-duplicated participant objects and all their participation periods within the scope;
- `events`: the canonical event stream, with actor, represented-principal, and recorder IDs;
- identity references used by supporting memory/revision lifecycle records.

The exported participant array includes people who only participated and never acted, as well as actors and recorders who appear in the event/lifecycle history.

## Legacy database migration

Existing databases gain the attribution columns additively. Historical events are not assigned invented people or retroactive participation periods.

Where an older event has no actor identity, the migration uses an explicit unattributed identity. Existing rows are not used to infer who was present in a conversation. New calls that omit an actor retain compatibility through explicit fallback identities by provenance:

- user → `ael:actor:unknown-user`
- assistant → `ael:agent:assistant`
- external → `ael:actor:unknown-external`
- system → `ael:system:runtime`

New multi-user integrations should always supply the authenticated participant ID. The fallbacks are compatibility markers, not acceptable substitutes for identity-aware production workflows.

## Current limits

- AEL stores the identity references and membership intervals; the host application is responsible for authenticating identities and supplying trustworthy IDs.
- A participation interval establishes membership in the chain, not message-level delivery, reading, or comprehension.
- The runtime does not infer responsibility or culpability from presence. Actor, authority, role, scope, and available evidence must be evaluated separately.
- The SQLite prototype does not add foreign-key constraints from every actor field to the participant registry; runtime validation rejects unregistered explicit actors.
