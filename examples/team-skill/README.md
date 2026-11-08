# Portable team skill-log examples

These examples test one portable record structure against three different classes of team learning. Two are manually curated from synthetic AEL ledger fixtures; one is derived from a real, public AEL repository change. None is an automatic extraction.

## Files

- [`portable-skill-log.json`](portable-skill-log.json) — check relationships across processing boundaries when work is divided into chunks. Synthetic scenario.
- [`source-grounded-claim-reconciliation.json`](source-grounded-claim-reconciliation.json) — preserve source definitions, populations and periods when synthesising findings that appear to conflict. Synthetic scenario.
- [`actor-provenance-authority-separation.json`](actor-provenance-authority-separation.json) — keep speaker identity, provenance and authority distinct when extending shared event paths. Derived from a real AEL code-path correction; independent skill review is still pending.
- [`REAL_REPOSITORY_LESSON.md`](REAL_REPOSITORY_LESSON.md) — origin, evidence and review limits for the third example.

## Why three examples?

The first scenario is an engineering/process lesson: locally correct chunks do not guarantee correctness across chunk boundaries.

The second scenario is an evidence-synthesis lesson: apparently conflicting figures may not be comparable if they measure different things, populations or periods. The candidate method keeps source claims separate until their comparability is established and avoids adding unsupported causation.

The third example comes from real repository work. When the AEL fixture gained multiple agents, its shared message path still applied human-only defaults to every speaker. The correction mapped message attribution using the registered speaker and added tests to prevent agent events acquiring human decision authority. The extracted practice is to audit every attribution field when new actor types enter an existing event path.

The three records use the same 14 top-level fields:

- identity and maturity of the candidate skill;
- problem pattern and conditions;
- generalised method;
- applicability;
- limitations;
- validation status and what remains unestablished;
- provenance;
- reuse guidance.

The content of the lessons differs. The examples also show that provenance details need not be identical: a synthetic scenario can point to a fixture and step numbers, while a real code change can point to a repository, pull request, commit, files and tests.

## Privacy and evidence boundaries

The two synthetic portable records exclude participant names and IDs, account/project/chat identifiers, and raw conversation text.

The repository-derived record also excludes participant names/IDs, account/project/chat identifiers and raw conversation text. It retains the public repository, PR, commit and source-file references so the implementation evidence can be independently inspected. That is source traceability, not anonymisation of the public project itself.

These examples demonstrate deliberately reduced records. They do not establish that anonymisation alone makes knowledge safe to distribute. In real use, source evidence remains subject to its original access and retention boundaries; only reviewed generalised knowledge should be considered for wider reuse.

## Validation limits

- The first two source scenarios are synthetic; each skill has passed only within its own fixture.
- The third lesson is grounded in a real merged code change and repository tests, but the extracted skill is still a candidate awaiting independent human/team review.
- The repository change does not establish that a live hosted multi-agent platform was integrated or that a production incident occurred.
- The examples do not establish a universal skill format or automatic extraction process.
- A matching outer record structure is a useful compatibility signal, not proof that the format captures every kind of team learning.
- Applicability and source quality must be checked again in the receiving team's context.

The goal is to carry useful, appropriately qualified knowledge as a file into a clean environment, without carrying the whole project history or depending on its database.
