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


## 6. Blind human scoring

The paired runner makes score-packets/score-A.zip and score-packets/score-B.zip. Send the two packets to assessors without the private condition key. Each packet includes SCORING_RUBRIC.md, scorecard.schema.json, scorecard-template.json, source code, acceptance report, submitted plan, final summary and a redacted observable timeline. Raw model requests/responses and the condition-configuration hash are deliberately omitted from the packet; preserve the original events.jsonl files separately for audit.

Each assessor should fill a separate scorecard for each blind label and submit both independently. Preserve original ratings and reasons before comparing them. Record disagreement; do not silently average away differences. Freeze the scorecards before using the private condition key to identify skill-on/off.

Use packet SHA-256 values in blinded-pair-report.json to verify you are scoring the produced packets. Human ratings should cite files, acceptance checks, or event sequence IDs. Do not rate hidden reasoning. One pair remains exploratory evidence.


## Pinned skill revision

The experiment accepts only the exact bytes at memoryprismv1/cognitive-interface-ai-skills/critical-thinking/SKILL.md, pinned to commit d1f23e2ad9dafd323940fc6b7a00f1700275d885 (Git blob SHA-1 d7134969b124e39c04e343bed2ce2475f64b9a64). The runner checks the blob identity and logs SHA-256. Substituting or editing the file fails before a model request is sent.

## Real local-model pilot

Merging PR #6 automatically triggers the real pilot because the workflow watches changes to its own workflow file on main. No extra setup click should be needed after merge. The workflow installs local Ollama on an ephemeral GitHub-hosted VM, pulls qwen2.5-coder:7b, validates the pinned skill, and executes a randomized pair using identical settings except for skill inclusion. The model is code-focused and the official model page lists the 7B variant as 4.7 GB: https://ollama.com/library/qwen2.5-coder. The workflow can also be re-run manually from Actions → CT A-B real local-model pilot → Run workflow.

Download the ct-ab-blind-score-packets artifact for assessors. Do not share the ct-ab-audit-evidence artifact with them before they freeze their scores; it contains the actual requests, including the skill text on the enabled condition. After scoring, inspect that audit evidence and the manifests to unblind the A/B conditions. The private key is not part of the uploaded artifacts.

This hosted pilot executes generated app code on an ephemeral VM, not a hardened sandbox. The checkout action does not persist credentials and the acceptance subprocess receives a restricted environment, but this is not a guarantee against arbitrary code. The real run is triggered only when the pilot workflow file itself is pushed to main, or manually via workflow_dispatch. It is separate from routine regression CI.
