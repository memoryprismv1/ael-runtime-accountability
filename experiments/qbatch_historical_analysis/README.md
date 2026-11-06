# Q-Batch historical cohort analysis — experimental prototype

This directory contains a **read-only, standard-library-only prototype** for inspecting historical Q-Batch evidence, identifying observable failure signatures, grouping comparable independent attempts, and applying a conservative four-attempt threshold.

It is deliberately separate from `testing_logger/` and the CT A/B live runner. It does not change raw evidence, the live event validator, workflow triggers, AEL Ledger, or rerun automation.

## Contents

- `qbatch_historical_analysis.py` — historical run reader, integrity verification, observed recording-profile inference, normalisation, failure classification, cohort comparability and manual rerun recommendation policy.
- `test_qbatch_historical_analysis.py` — eighteen deterministic tests, including the four observed historical failure signatures, explicit provenance binding, legacy compatibility, cohort eligibility, paired A/B counting, tampering and unknown formats.
- `reports/2026-11-03-ct-ab-failure-cohort.md` and `.json` — a read-only analysis of eight run logs from four archived CT A/B workflow attempts, including the 4 November 2026 replay against the current reader.

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

The reader verifies event sequence and hash chaining, referenced evidence sizes and SHA-256 hashes, context snapshot binding when present, explicit capture-profile/runner provenance binding when present, and the final event-stream checksum when present. Legacy manifests without provenance remain readable but cannot qualify for a comparable cohort. Removing provenance from a new manifest is detected because the values remain bound into its first event. A missing checksum is reported as partial integrity. Unknown schema/logger labels and unknown event vocabularies do not qualify for diagnosis. The four original archives were replayed against the current reader on 4 November 2026: all 8 run logs passed integrity verification, 920 evidence references were re-hashed, and there were zero read failures.

## Important limitations

- Historical schema/logger labels were reused while event-capture capabilities evolved. The prototype infers *observed recording profiles* from available evidence; it cannot infer that a missing event was impossible or unsupported by the producer.
- Older manifests do not record the runner implementation revision, worktree cleanliness, or an explicit capture-profile identity. Their comparability identity is incomplete, so even a matching failure signature cannot qualify them for a four-attempt diagnosis cohort.
- New CT A/B runs record a versioned list of supported capture capabilities, its SHA-256, the exact runner source revision when available, and whether the source worktree was clean. These are bound to `run_started` and compared across A/B. A missing Git revision or unknown worktree state is recorded as unavailable and blocks cohort eligibility rather than being guessed.
- A and B are paired conditions within one workflow attempt. They count as one independent attempt, not two.
- Four comparable independent attempts are the minimum threshold for batch diagnosis eligibility; they are not a guarantee of statistical certainty or proof of root cause.
- A rerun recommendation requires a recorded targeted fix and a passing regression test, and remains manual-approval-only. This prototype never triggers a workflow.
- The included historical report links to source GitHub Actions runs/artifacts. The report does not embed private raw audit traces or model prompt/response contents; source artifact retention is controlled by GitHub.

This is an experimental post-processor. Its deterministic tests are part of routine CI; the reader remains separate from the live logger, live experiment controls, and rerun automation.


## Preserved historical reports

- [Q-Batch source-artifact archive inventory, 5 November 2026](reports/2026-11-05-archive-inventory.json) — source workflow artifact IDs, expiry metadata, file sizes and hashes. It records metadata only; the raw ZIP/TAR bytes are not stored in this repository.

- [Historical Q-Batch record, 5 November 2026](reports/2026-11-05-historical-record.md) and [machine-readable record](reports/2026-11-05-historical-record.json).
- [Raw-log verification, 5 November 2026](reports/2026-11-05-raw-log-verification.md) and [machine-readable result](reports/2026-11-05-raw-log-verification.json).
- [First-pass run behaviour](reports/2026-11-06-first-pass-run-behaviour.md).
- [Kanban pair investigation](reports/2026-11-06-kanban-pair-investigation.md).

These are descriptive records, not model-efficacy findings. See the reports for the scope and limitations of each analysis.
