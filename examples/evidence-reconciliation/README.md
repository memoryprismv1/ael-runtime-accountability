# Second portable-skill test: evidence reconciliation

This is a separate synthetic scenario used to test whether the portable skill-log format can express a different kind of team learning from the chunk-boundary example.

## Scenario

A human requests a source-grounded brief. Four separately identified agents contribute:

- Evidence research records a synthetic finding about metered consumption.
- Counterevidence review records a second synthetic finding about billed consumption.
- Synthesis initially considers a combined narrative.
- Verification points out that the two measures have different definitions, district coverage and comparison periods, and that neither source establishes a cause.

The human rejects the combined causal narrative and selects a brief that reports the two findings separately with their measurement boundaries intact. An independent verification message checks the final wording before the human records completion.

All source material and quantities are invented for this fixture. This is not a claim about actual water use or any real organisation.

## Run with a clean database

From the repository root, the shared runner can execute this scenario without using the multi-agent chunk fixture:

```bash
python examples/multi-user-workflow/run_fixture.py \
  --participants examples/evidence-reconciliation/participants.csv \
  --workflow examples/evidence-reconciliation/workflow.csv \
  --account evidence-fixture-account \
  --project source-brief-demo \
  --chat source-reconciliation-demo \
  --out handoffs/evidence-reconciliation-receipt.json
```

The runner uses a temporary SQLite database unless `--db` is supplied.

## Portable skill record

[`examples/team-skill/source-grounded-claim-reconciliation.json`](../team-skill/source-grounded-claim-reconciliation.json) uses the same top-level record structure as the chunk-boundary skill but contains a different lesson: compare source definitions, populations and time periods before synthesising apparent conflicts, and do not add unsupported causation.

The portable file omits participant names and IDs, account/project/chat identifiers, and raw dialogue. It retains the source fixture path and relevant step references, as does the first skill.

## What this second test evaluates

- Can the same outer record format express a different class of reusable practice?
- Can it retain conditions, a method, applicability, limitations, validation status and provenance?
- Can it distinguish source disagreement from non-comparability?
- Does it preserve the boundary between a candidate skill and a universally validated rule?

This remains a manual extraction from synthetic evidence. Passing this fixture is not proof of the lesson in real research or operational settings, and it does not justify automatic skill extraction by itself.
