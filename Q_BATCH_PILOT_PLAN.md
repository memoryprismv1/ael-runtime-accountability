# Q-Batch Pilot Plan — AEL Runtime Accountability

**Status:** Real-model skill-on/skill-off pilot has no valid pair; method demonstration should be tested separately  
**Method:** Q-Batch of Evidence  
**Purpose:** Preserve independently inspectable evidence in batches and enable comparison without requiring a fragile, expensive back-to-back model run. The Critical Thinking pilot is one possible application, not proof of the Q-Batch method itself.

## Important distinction: the pilot is too heavy to test the method

The existing real-model task has failed in both conditions in repeated attempts: tool-protocol/no-tool loops in earlier attempts, then a first-request timeout in both A and B. No valid pair reached independent acceptance scoring. This is evidence that the current task/model/runner combination is too heavy or brittle for a first demonstration—not evidence for or against Critical Thinking, and not a verdict on Q-Batch.

Do not use another expensive real-model attempt as the first test of Q-Batch's value. First test the method with a small deterministic fixture whose expected result is known. The fixture should reproduce a specific sequential-comparison problem, such as order-dependent outcomes caused by shared mutable state, then compare that with independent runs from a clean recorded baseline. Q-Batch should preserve the run order, baseline/state identity, outcomes, and evidence needed to expose the confound.

Keep three claims separate:

- **Logger integrity:** event chains, checksums, and artifact references detect missing or changed evidence.
- **Q-Batch methodology:** a frozen evidence batch makes independently executed conditions inspectable and reveals a known confound that a naive sequential comparison obscures.
- **Real-model efficacy:** whether the Critical Thinking skill improves task performance. The current pilot has not established this.

## Plain-English status

The experiment harness already exists. This plan is not a replacement for it.

- The experiment is a paired software-building task: one blind condition has the pinned Critical Thinking skill and the other does not.
- The real-model workflow uses a disposable GitHub-hosted Linux runner, installs Ollama, downloads `qwen2.5-coder:7b`, verifies the pinned skill revision, and runs both conditions.
- Two earlier real-model attempts failed as harness/model-tool-protocol runs: first, the model encoded tool calls as response text; second, it repeatedly produced prose/echoes without calling tools. Neither attempt produced a valid comparison or ran the independent acceptance suite.
- The no-tool loop handling and audit-event schema have since been updated. That is a code fix, not proof the next real-model attempt will pass.
- The repository's routine tests and synthetic preflight are instrumentation checks. They do not establish that the skill improves task performance.

## Frozen protocol source

The controlling experiment instructions are in [experiments/ct_ab/README.md](experiments/ct_ab/README.md), with the executable workflow in [.github/workflows/ct-ab-real-model-pilot.yml](.github/workflows/ct-ab-real-model-pilot.yml). Do not invent a new task, prompt, rubric, model, or skill revision for this pilot.

Protocol settings currently declared by the workflow:

- Model: `qwen2.5-coder:7b`
- Temperature: `0`
- Context setting: `16384`
- Prediction limit: `1200`
- Request timeout: `600` seconds (the GitHub Actions workflow explicitly passes `--timeout 600`; the CLI's general-purpose default remains 180 seconds)
- Maximum agent turns: `24`
- Maximum tool calls: `60`
- Skill source: `memoryprismv1/cognitive-interface-ai-skills`, commit `d1f23e2ad9dafd323940fc6b7a00f1700275d885`, file `critical-thinking/SKILL.md`
- Both blind runs use the same model, client brief, starter workspace, tool definitions and resource limits. The run order and mapping of blind A/B to skill-off/skill-on are randomized. The controller key stays separate until scoring is frozen.

## Acceptance gate for a valid pair

Treat a real-model pair as **valid only if all** of these hold:

1. Both conditions finish; a failed or incomplete condition makes the pair invalid/incomplete.
2. The harness captures observed tool calls, commands, file changes and test results; a model's claim that it did work is not proof.
3. Both run logs and their referenced artifacts pass validation, including hashes and required event types.
4. Controlled manifest fields match; task and condition configuration hashes are preserved.
5. The independent acceptance suite runs and produces a report for each condition.
6. The blinded pair report and blind scoring packets are generated.
7. Raw request/response audit evidence and the controller key remain withheld from assessors until their independent scorecards are frozen.

The independent acceptance score is an objective task result. Human assessor ratings are additional qualitative evidence, not a substitute. Agreement between assessors is not proof of correctness. Do not infer skill effectiveness from one pair alone.

## Q-Batch evidence handling

Preserve the run as an immutable evidence batch. Do not rerun or reconstruct missing evidence and silently combine it with the original.

For each attempt, record:

- workflow run URL and run ID;
- commit SHA and pinned skill revision;
- final workflow/job status;
- whether both conditions finished;
- whether the instrumentation and log-validation gates passed;
- whether independent acceptance ran for both conditions;
- names and hashes of uploaded artifacts;
- explicit failure/incomplete reasons and any recovery code changes since the previous attempt.

Keep blind scoring packets separate from full audit evidence. The audit traces contain raw model requests/responses and may reveal the condition. Do not expose the controller key or audit evidence before blind scoring is frozen.

## Run history

### Attempt 1 — invalid
Run `39592787189`: both conditions returned tool calls encoded in response text rather than the structured tool-call field. Tool dispatch did not occur; both exhausted the 24-turn budget. Acceptance was not run. This is a harness/model protocol failure, not evidence for or against the skill.

### Attempt 2 — invalid
Run `39597455540`: after the text-tool-call fallback, both conditions fell into repeated no-tool responses/echoes and exhausted the 24-turn budget. Acceptance was not run. Issue #8 added bounded recovery and loop detection. Again, this is not efficacy evidence.

### Attempt 3 — status
The audit event schema was subsequently corrected to include the recovery-attempt and loop-detection events introduced by the fix. The latest commit visible during this review is `1b0ee8ad691a70165c7c211d3ba92c048619cd14`, which adds this Q-Batch plan. A new real-model run has **not been verified from this review**, so do not assume it ran or passed.

## What happens next

1. Routine CI and the synthetic preflight should pass on the current main branch.
2. Run the existing **CT A-B real local-model pilot** workflow from GitHub Actions, or let its configured push trigger run when a relevant harness/workflow file changes. This downloads a multi-gigabyte model and can take a long time.
3. Freeze the resulting workflow artifacts as one attempt.
4. If the run is invalid, use its audit evidence to fix the specific harness failure, then create a new attempt; do not score an invalid pair.
5. If valid, distribute only the blind scoring packets, collect independent scorecards, freeze those scorecards, and only then inspect the condition key/audit evidence and compare.

## Execution boundary

The GitHub repository connection used to prepare this document cannot itself start or observe a new Actions workflow run. The real-model workflow is already present and has a manual **Run workflow** option in GitHub Actions. No local Ollama installation on the user's computer is needed for that hosted workflow. A run still must actually occur before any result can be claimed.


### Attempt 3 — invalid: first-turn model request timeout

Run [39730856613](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39730856613), commit `5abd6ced1b5b2a35310b4e7b28c7fbc485bcc150`:

- Skill revision verification, Ollama installation, 4.7 GB model download, and local model inventory all passed.
- Both A and B failed on turn 1 with `model request failed ... timed out` under the 180-second request timeout.
- The pair report correctly says `RUN_INCOMPLETE`; instrumentation validation failed because neither run reached planning/tool/command events; independent acceptance was not run.
- Therefore this is not a scored pair and says nothing about the skill's effect.

**Recovery action:** the workflow now passes a 600-second per-request timeout while keeping the model, pinned skill, task, temperature, context, prediction limit, turn/tool limits and blinded paired design unchanged. This is an operational allowance to test whether the hosted CPU runner can complete the first response, not a change to the task or rubric. The next attempt remains pending until a new workflow run is observed. It must be preserved as a new independent evidence batch; do not merge it with this failed batch.


## Recommended next step: small method test before another model pilot

Use a deterministic, low-cost fixture to show the distinction between (a) two conditions executed sequentially against shared state and (b) the same conditions run independently from clean, recorded baselines. Intentionally make the shared-state outcome order-dependent, then verify that the batch records enough evidence to identify that dependency and compare the isolated runs.

The method test should complete without Ollama, model downloads, generated application code, or human scoring. Its report must say explicitly that it is synthetic and establishes only the demonstrated failure mode and evidence handling. It must not be described as proof that Q-Batch is universally better than A/B testing.

Only return to the real-model skill pilot if the skill-effectiveness question is still worth its execution cost and a suitably lightweight, reliable model/task setup is available. Any new attempt remains a separate immutable evidence batch.


## Deterministic method demonstration (implemented)

The model-free demonstration is implemented in `experiments/ct_ab/method_demo.py` and tested by `experiments/ct_ab/test_method_demo.py`. CI runs the unit test and creates an evidence artifact named `ct-ab-method-demo-evidence`.

It compares six logged runs:
- A then B against shared state;
- B then A against shared state;
- A and B independently, each from a fresh baseline.

The fixture is intentionally stateful: the first condition sees a clean baseline, and the next condition inherits the previous condition's state. The expected result is order dependence in the sequential comparisons and comparable clean-baseline outcomes in the isolated runs. Every run's event chain, checksum and evidence references are validated before the method report is marked PASS.

**Interpretation boundary:** this is a deterministic demonstration that a particular sequential carryover confound can be exposed by clean-baseline runs and an evidence batch. It is not proof of universal superiority over A/B testing, and it says nothing about Critical Thinking skill efficacy.
