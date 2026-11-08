# Portable team skill-log example

This example shows one possible output of distilling a general lesson from an AEL ledger without distributing the project transcript or participant identity data.

## Files

- `portable-skill-log.json` is a manually curated, machine-readable example of a portable team skill record.

## What it demonstrates

The synthetic multi-agent fixture records an initial bounded-processing proposal, an independent challenge about cross-boundary dependencies, a human decision to evaluate the first approach, a validation finding, a revised approach, and a final human decision after independent validation.

The portable record extracts only the general lesson: locally correct chunks do not guarantee correctness across chunk boundaries. It records applicability conditions, a reusable method, limitations, validation status and a reference to the synthetic fixture steps that support the extraction.

It intentionally excludes participant names and IDs, account/project/chat identifiers, and raw conversation text. The source step references preserve a route back to the synthetic evidence without embedding that evidence in the portable file.

## Important limits

- This is a manually curated demonstration, not an automatic skill extractor.
- The source scenario is synthetic. The skill has only passed within that fixture; external applicability is untested.
- This is a candidate skill, not an instruction that every team must follow.
- Anonymising an experience does not prove the resulting lesson is universally applicable.
- In a real deployment, source evidence would remain subject to its original access and retention boundaries. Only the reviewed, generalised skill would be distributed.

The intent is to explore a file that can travel with a team's repository and provide useful prior learning even when a test starts with a clean database.
