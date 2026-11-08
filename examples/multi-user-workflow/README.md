# Multi-agent participant and skill-learning fixture

This fixture exercises the AEL schema-v3 participant registry and actor attribution without requiring a real multi-user chat service or a pre-populated database.

## Participants

`participants.csv` contains four humans and four explicitly typed agents:

- Human requester, coordinator, passive manager and decision-maker.
- Analysis agent, review agent, implementation agent and validation agent.

Importing the roster registers identities; it does **not** add them to a conversation. Participation begins only through explicit `join` steps.

## Scenario

`workflow.csv` drives 27 deterministic steps:

1. The human requester describes a resource-constrained processing problem.
2. An analysis agent proposes bounded chunks.
3. A separate review agent challenges the proposal by identifying dependencies that may cross chunk boundaries.
4. The analysis agent revises its proposal. The reviewer also proposes an alternative.
5. A human selects an initial prototype for evaluation. This is an attributed decision in the fixture, not an implemented permission policy.
6. The implementation agent reports the prototype ready; an independent validation agent finds a boundary defect.
7. The human rejects the initial approach. The review agent proposes overlap-aware processing and boundary reconciliation.
8. The human selects the revised approach; the implementation agent reports the change; the validation agent records a pass for the synthetic boundary cases; the human records completion.
9. A passive manager leaves without ever acting. The requester leaves and rejoins, retaining the same identity across two participation periods.

Agent messages are stored with the registered agent as actor, assistant provenance, and no human decision authority. Human messages retain user provenance. Human branch decisions retain the human actor and direct-user authority attribution. Distinct agent identities are not collapsed into one generic assistant.

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

## Portable skill example

[`examples/team-skill/portable-skill-log.json`](../team-skill/portable-skill-log.json) is a manually curated, anonymised candidate skill distilled from the synthetic ledger scenario. It contains the generalised boundary-checking lesson, applicability, method, limitations, validation status and source fixture step references. It omits participant identities, scope identifiers and raw dialogue.

See [the skill example README](../team-skill/README.md) for what this does and does not demonstrate. This is not an automatic extractor and does not establish external validity.

## Fixture boundaries

- This is a deterministic ledger and attribution test, not a live ChatGPT multi-agent adapter.
- The fixture demonstrates recorded disagreement and distinct contributions; it does not simulate independent model cognition.
- A recorded human decision is not proof of an external permission check. AEL records actor and claimed/recorded authority; the host remains responsible for actual authentication and access control.
- The exported ledger is the evidence source. The portable skill file is a deliberately reduced, reviewed example, not a transcript replacement.
