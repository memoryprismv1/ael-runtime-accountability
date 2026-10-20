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

## Comparison testing
compare_environments.py runs the same standard-library test command separately inside each environment with distinct AEL_PATH and PYTHONPATH. It records per-test outcomes and compares shared tests pairwise across all specified environments, flags baseline-pass-to-experiment-failure regressions and reports tests unique to each tree. Repeat --environment NAME=PATH for more environments. CI tests Python 3.11, 3.12 and 3.13 and preserves a JSON report.

Interpretation limit: the first harness tests deterministic software regressions. It does not prove CT improves reasoning. That requires a fixed evaluation set, controlled model/version/settings, isolated model state and explicit case-note/plan assessment criteria.
