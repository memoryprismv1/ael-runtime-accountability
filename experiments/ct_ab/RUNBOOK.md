# CT A/B experiment runbook

## The current gate

The experiment has not produced any scored real-model result. The repository's logger, paired runner and client task are tooling under test. The mock-model integration test is deliberately labelled synthetic.

## 1. Check local Ollama

From the repository root, run:

    python -m experiments.ct_ab.paired_runner doctor

Use the exact model name reported by Ollama. This command sends no prompt.

## 2. Supply the actual Critical Thinking skill

Use the existing file you intend to evaluate. The experiment refuses empty files and records the file SHA-256 in the separate controller key. Never copy the skill file into a model's writable workspace. The controller adds the verbatim text only to the enabled condition's system message and hashes the configuration to prove which condition was loaded.

## 3. Run one pair in an isolated machine

The pair must run in a disposable VM/container without access to secrets or important files. The current acceptance executor starts model-generated app.py as the current OS user; the harness is not a security sandbox.

    python -m experiments.ct_ab.paired_runner run-pair --output <NEW_EMPTY_OUTPUT_DIRECTORY> --model <EXACT_LOCAL_MODEL_NAME> --ct-skill <PATH_TO_ACTUAL_SKILL_FILE> --allow-host-execution

The CLI requires the explicit host-execution acknowledgement. This flag does not sandbox the process.

## 4. Review the blinded outputs

Review blinded-pair-report.json, A/B source bundles, per-run acceptance-report.json files and events.jsonl traces without opening the separate controller key. Freeze independent scores before revealing which blind label included the skill.

The independent acceptance suite checks the home-page automation hooks, three-column board contract, input validation, create/edit/move/delete lifecycle, missing-card handling, and persistence across server restarts. The suite is a fixed software-correctness proxy, not a universal measure of reasoning quality.

## 5. What constitutes evidence

A passing CI run proves only that the harness functions in its mock rehearsal. A completed local pair proves the same model completed two runs and leaves inspectable evidence. A difference in acceptance score on one pair is exploratory, not a general causal finding. Stronger claims require repeated pairs, independent scoring, preserved disagreement, and analysis of differences in implementation quality and resources.

Never claim a real-model experiment ran unless the model requests/responses, skill file hash, both completed logs, acceptance reports and final pair validation exist.
