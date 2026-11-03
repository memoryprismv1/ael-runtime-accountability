# Q-Batch historical cohort analysis — experimental prototype

This directory contains a **read-only, standard-library-only prototype** for inspecting historical Q-Batch evidence, identifying observable failure signatures, grouping comparable independent attempts, and applying a conservative four-attempt threshold.

It is deliberately separate from `testing_logger/` and the CT A/B live runner. It does not change raw evidence, the live event validator, workflow triggers, AEL Ledger, or rerun automation.

## Contents

- `qbatch_historical_analysis.py` — historical run reader, integrity verification, observed recording-profile inference, normalisation, failure classification, cohort comparability and manual rerun recommendation policy.
- `test_qbatch_historical_analysis.py` — fourteen deterministic tests, including the four observed historical failure signatures, cohort eligibility, paired A/B counting, missing runner provenance, tampering and unknown formats.
- `reports/2026-11-03-ct-ab-failure-cohort.md` and `.json` — a read-only analysis of eight run logs from four archived CT A/B workflow attempts.

## Run tests

From the repository root:

```bash
python -m unittest discover -s experiments/qbatch_historical_analysis -p 'test_*.py' -v
```

## Analyse an evidence archive

First extract the GitHub Actions audit artifacts so that the input directory contains folders named `qbatch-run-<workflow-run-id>-audit`, each with `runs/run-a/` and `runs/run-b/` and their original manifests, event streams and referenced artifacts.

Then run from the repository root:

```bash
python experiments/qbatch_historical_analysis/qbatch_historical_analysis.py \
  --input /path/to/extracted-qbatch-archives \
  --output /path/to/cohort-report.json \
  --markdown /path/to/cohort-report.md
```

The reader verifies event sequence and hash chaining, referenced evidence sizes and SHA-256 hashes, context snapshot binding when present, and the final event-stream checksum when present. A missing checksum is reported as partial integrity. Unknown schema/logger labels and unknown event vocabularies do not qualify for diagnosis.

## Important limitations

- Historical schema/logger labels were reused while event-capture capabilities evolved. The prototype infers *observed recording profiles* from available evidence; it cannot infer that a missing event was impossible or unsupported by the producer.
- Older manifests do not record the runner implementation revision. Their comparability identity is incomplete, so even a matching failure signature cannot qualify them for a four-attempt diagnosis cohort.
- A and B are paired conditions within one workflow attempt. They count as one independent attempt, not two.
- Four comparable independent attempts are the minimum threshold for batch diagnosis eligibility; they are not a guarantee of statistical certainty or proof of root cause.
- A rerun recommendation requires a recorded targeted fix and a passing regression test, and remains manual-approval-only. This prototype never triggers a workflow.
- The included historical report links to source GitHub Actions runs/artifacts. The report does not embed private raw audit traces or model prompt/response contents; source artifact retention is controlled by GitHub.

This is an experimental post-processor, not yet integrated into Q-Batch's routine CI or live experiment controls.
