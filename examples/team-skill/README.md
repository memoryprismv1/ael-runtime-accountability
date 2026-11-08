# Portable team skill-log examples

These examples test one portable record structure against two different classes of team learning. Both are manually curated from synthetic AEL ledger fixtures; neither is an automatic extraction.

## Files

- [`portable-skill-log.json`](portable-skill-log.json) — check relationships across processing boundaries when work is divided into chunks.
- [`source-grounded-claim-reconciliation.json`](source-grounded-claim-reconciliation.json) — preserve source definitions, population and periods when synthesising findings that appear to conflict.

## Why two examples?

The first scenario is an engineering/process lesson: locally correct chunks do not guarantee correctness across chunk boundaries.

The second scenario is an evidence-synthesis lesson: apparently conflicting figures may not be comparable if they measure different things, populations or periods. The candidate method keeps source claims separate until their comparability is established and avoids adding unsupported causation.

The two examples use the same top-level record fields:

- identity and maturity of the candidate skill;
- problem pattern and conditions;
- generalised method;
- applicability;
- limitations;
- validation status and what remains unestablished;
- provenance back to a synthetic source fixture;
- reuse guidance.

The content of the lessons differs. The format is intended to preserve that difference rather than force unrelated knowledge into one generic recipe.

## Privacy and evidence boundaries

Both portable records intentionally exclude participant names and IDs, account/project/chat identifiers, and raw conversation text. Each retains a source file and step references so the source evidence can be found in the repository without embedding the transcript in the portable skill.

These examples demonstrate a deliberately reduced, reviewed record. They do not establish that anonymisation alone makes knowledge safe to distribute. In real use, source evidence would remain subject to its original access and retention boundaries; only reviewed generalised knowledge would be considered for wider reuse.

## Validation limits

- Both source scenarios are synthetic; neither proves real-world effectiveness.
- Each skill is validated only within its own fixture.
- The examples do not establish a universal skill format, automatic extraction process, or approval system.
- A matching outer record structure is a useful compatibility signal, not proof that the format captures every kind of team learning.
- Applicability and source quality must be checked again in the receiving team's context.

The goal at this stage is modest: see whether a team can carry useful, appropriately qualified knowledge as a file into a clean environment, without carrying the whole project history or depending on its database.
