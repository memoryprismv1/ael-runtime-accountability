# Portable team skill-log examples

These examples test one portable record structure against three different classes of team learning. Two are manually curated from synthetic AEL ledger fixtures; one is derived from a real AEL repository correction. None is an automatic extraction.

## Files

- [`portable-skill-log.json`](portable-skill-log.json) — check relationships across processing boundaries when work is divided into chunks. Synthetic scenario.
- [`source-grounded-claim-reconciliation.json`](source-grounded-claim-reconciliation.json) — preserve source definitions, populations and periods when synthesising findings that appear to conflict. Synthetic scenario.
- [`actor-provenance-authority-separation.json`](actor-provenance-authority-separation.json) — add explicit speaker-aware classification to a shared event path without inferring authority from speaker type. Derived from a real AEL fixture-runner correction; the extraction has had a critical scope review and remains pending human/team adoption review.
- [`REAL_REPOSITORY_LESSON.md`](REAL_REPOSITORY_LESSON.md) — source experience and evidence boundary.
- [`REVIEW_ACTOR_PROVENANCE_SKILL.md`](REVIEW_ACTOR_PROVENANCE_SKILL.md) — critical scope review, corrections and outstanding adoption review.

## Why three examples?

The first scenario is an engineering/process lesson: locally correct chunks do not guarantee correctness across chunk boundaries.

The second scenario is an evidence-synthesis lesson: apparently conflicting figures may not be comparable if they measure different things, populations or periods.

The third example is a real repository engineering correction: the fixture runner had human-only message defaults, then gained agent speakers. The correction introduced speaker-aware field mapping. The revised lesson is deliberately limited to that evidence: use explicit speaker-aware classification, but do not infer authentication or authority from a participant type.

## Shared record structure

All three records use the same 14 top-level fields:

- identity and maturity of the candidate skill;
- problem pattern and conditions;
- generalised method;
- applicability;
- limitations;
- validation status and what remains unestablished;
- provenance;
- reuse guidance.

The records show that provenance needs different shapes depending on origin. Synthetic scenarios use fixture paths and step references; a repository-derived lesson uses a repository, PR, commit, source files and tests. Shared field names do not imply identical evidence or equal validation strength.

## Privacy and evidence boundaries

The two synthetic portable records exclude participant names and IDs, account/project/chat identifiers, and raw conversation text.

The repository-derived record also excludes fixture participant names/IDs, account/project/chat identifiers and raw dialogue. It retains public repository and code-history references so its origin can be inspected. This is source traceability, not anonymisation of the public repository itself.

## Validation limits

- The first two source scenarios are synthetic; each skill is validated only within its own fixture.
- The third lesson is based on a real AEL fixture-runner correction and its integration test, not a production incident or live hosted platform.
- The fixture maps human messages to `user_direct` as a scenario convention. That is not authentication or permission evidence and must not be copied as a production default.
- The third scenario asserts human and agent cases; service/system/unknown branches are not all independently exercised there.
- The third extraction has had a critical scope review (see `REVIEW_ACTOR_PROVENANCE_SKILL.md`) but remains pending human/team adoption review.
- Three examples do not establish a universal skill schema or automatic extraction process.
- Applicability and source quality must be checked again in the receiving team's context.

The goal is to carry useful, qualified knowledge into a clean environment without carrying the whole project history or depending on its database.
