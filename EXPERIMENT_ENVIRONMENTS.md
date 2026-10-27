# AEL experiment environments

This structure deliberately keeps a full CT copy of the baseline tree. The root runtime.py and ael_chat.py remain the V2.8.1 control; ct/ contains the isolated critical-thinking task-precommitment experiment.

## Path inheritance
AEL_PATH names the active environment root. The root launcher resolves it, validates experiment.json, and passes the absolute path to child processes. It sets their working directory and Python import path to the same root. CT entry points refuse a path that disagrees with their own directory; the CT runtime validates the manifest and pinned dependencies on startup. Keep imports inside the selected environment.

From the repository root:
- python run_ael.py runtime --help
- python run_ael.py --path ct runtime task --help
- python run_ael.py --path ct chat
- python compare_environments.py --out comparison-report.json

## Dependency manifests
Each environment has an experiment.json. Its requirements map records exact versions, paths, required/optional status, source revision and integrity hashes. SHA-1 Git blob hashes and SHA-256 are supported. Missing required dependencies, hash mismatch, path escapes or a git: version inconsistent with source_commit fail closed.

To create another experiment, copy an environment, give it a unique experiment_id and list the desired pinned skills. A future ct_xyz/ may declare Critical Thinking and XYZ at separate versions.


## Manifest-driven skill object

The active environment's `experiment.json` is the source of truth for the complete skill set. The task-precommitment loader builds `skill_obj` from every entry in `requirements`; it does not assume that Critical Thinking is the only skill. Each entry pins a version, environment-relative path, required/optional status, and integrity data (`source_blob_sha` and/or `sha256`). Git-based versions must match `source_commit`. Missing required skills, hash mismatches, or paths escaping the active environment fail closed. Missing optional skills are omitted.

`AEL_PATH` selects the runtime/environment tree; it is not a skill selector. The launcher passes the selected root to child processes, and the selected environment's manifest determines its skill object. For example, a future `ct_xyz/` environment can declare Critical Thinking and XYZ at independent pinned versions. Prompts include all loaded skills, and the audit event/artifact metadata records a stable `skill_obj_sha256` plus each skill's provenance. Existing single-skill audit columns are retained as compatibility fields for the primary Critical Thinking dependency.

The skill object's fingerprint is an identity/provenance checksum, not a quality score and not evidence that a model followed a skill.

## Comparison testing
compare_environments.py runs the same standard-library test command separately inside each environment with distinct AEL_PATH and PYTHONPATH. It records per-test outcomes and compares shared tests pairwise across all specified environments, flags baseline-pass-to-experiment-failure regressions and reports tests unique to each tree. Repeat --environment NAME=PATH for more environments. CI tests Python 3.11, 3.12 and 3.13 and preserves a JSON report.

Interpretation limit: the first harness tests deterministic software regressions. It does not prove CT improves reasoning. That requires a fixed evaluation set, controlled model/version/settings, isolated model state and explicit case-note/plan assessment criteria.

## CT model-output evaluation pilot
The efficacy question is a separate experiment. See [CT_EVALUATION_PLAN.md](CT_EVALUATION_PLAN.md) and the fixed [benchmark v1](ct-evaluation/benchmark-v1.json). The ten closed-world cases cover numerical reconciliation, category overlap, provenance/state mismatch, competing explanations, falsification of a preferred attribution, updating after correction, clock normalization, confounding, a simple-task control, and observation-versus-explanation.

The conditions are baseline (no CT skill), CT (the exact pinned skill genuinely loaded), and optional neutral format-only control. Keep model/version/task/evidence/tools/settings controlled, use isolated sessions, capture raw responses, score visible answers against the same fixed rubric, and retain case-level results. A ten-task pilot is exploratory; it cannot establish general reasoning capability or prove transfer across models.

The root-level script ct-evaluation.py creates a blank JSON scorecard, validates it, and summarizes manually entered scores. It does not call a model or automatically judge answers. Focused harness tests can be run without any model inference:

- python ct-evaluation.py init --output ct-evaluation/run.json --model MODEL_NAME --model-version VERSION
- Optional neutral control: add --include-neutral
- python ct-evaluation.py validate ct-evaluation/run.json --require-complete
- python ct-evaluation.py report ct-evaluation/run.json --out ct-evaluation/report.json
- python ct-evaluation/test_harness.py

Record the CT skill commit/blob from ct/experiment.json, exact model/provider/version/configuration, condition order, isolation method, deviations and assessor notes. Do not claim a CT result unless the condition actually loaded the pinned skill. Do not treat CI success as evidence of model quality. Actual inference requires an accessible model/runtime; the evaluation harness itself performs no inference.
