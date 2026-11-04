# Q-Batch Pilot Plan — AEL Runtime Accountability

**Status (4 November 2026):** No valid real-model skill-on/skill-off pair. Deterministic method demonstration is implemented. Current activity is stabilisation and historical compatibility verification; no new real-model attempt is planned in this cycle.  
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


## Current work order — stabilisation only (4 November 2026)

1. The deterministic Q-Batch method demonstration is implemented and is covered by routine CI. Do not rebuild it or add methodology features during the current stabilisation window.
2. The four original audit archives have now been replayed against the current historical reader. All eight logs passed integrity verification; 920 evidence references were re-hashed; there were zero read failures. See the current replay record in `experiments/qbatch_historical_analysis/reports/2026-11-03-ct-ab-failure-cohort.md`.
3. Preserve the historical conclusion: four distinct observed failure signatures, one independent workflow attempt per signature, zero eligible diagnostic cohorts. Missing historical provenance remains missing; do not infer or backfill it.
4. Stabilise the existing repeated-plan failure path with the smallest correction and a deterministic regression test. A duplicate `submit_plan` after a successful plan must stop the runner rather than consume the remaining turn budget.
5. Run routine CI and reconcile documentation. Do not run the multi-gigabyte real-model workflow in this stabilisation cycle.

No new Q-Batch features, analytics, storage mechanisms, dashboard, automatic reruns, or experiment redesign are in scope.

## Execution boundary

The GitHub repository connection used to prepare this document cannot itself start or observe a new Actions workflow run. The real-model workflow is already present and has a manual **Run workflow** option in GitHub Actions. No local Ollama installation on the user's computer is needed for that hosted workflow. A run still must actually occur before any result can be claimed.


### Attempt 3 — invalid: first-turn model request timeout

Run [39730856613](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39730856613), commit `5abd6ced1b5b2a35310b4e7b28c7fbc485bcc150`:

- Skill revision verification, Ollama installation, 4.7 GB model download, and local model inventory all passed.
- Both A and B failed on turn 1 with `model request failed ... timed out` under the 180-second request timeout.
- The pair report correctly says `RUN_INCOMPLETE`; instrumentation validation failed because neither run reached planning/tool/command events; independent acceptance was not run.
- Therefore this is not a scored pair and says nothing about the skill's effect.

**Recovery action:** the workflow now passes a 600-second per-request timeout while keeping the model, pinned skill, task, temperature, context, prediction limit, turn/tool limits and blinded paired design unchanged. This is an operational allowance to test whether the hosted CPU runner can complete the first response, not a change to the task or rubric. The next attempt remains pending until a new workflow run is observed. It must be preserved as a new independent evidence batch; do not merge it with this failed batch.


## Deterministic method test completed

The no-model order/carryover demonstration described below is implemented and included in routine CI. It establishes one specific sequential carryover confound and verifies that independent clean-baseline runs expose it. It does not prove universal superiority over A/B testing and does not provide evidence about Critical Thinking skill efficacy.

A real-model efficacy attempt is not part of the current stabilisation work. Any future decision to run one must be made separately; the current plan does not authorise a new expensive model workflow.


## Deterministic method demonstration (implemented)

The model-free demonstration is implemented in `experiments/ct_ab/method_demo.py` and tested by `experiments/ct_ab/test_method_demo.py`. CI runs the unit test and creates an evidence artifact named `ct-ab-method-demo-evidence`.

It compares six logged runs:
- A then B against shared state;
- B then A against shared state;
- A and B independently, each from a fresh baseline.

The fixture is intentionally stateful: the first condition sees a clean baseline, and the next condition inherits the previous condition's state. The expected result is order dependence in the sequential comparisons and comparable clean-baseline outcomes in the isolated runs. Every run's event chain, checksum and evidence references are validated before the method report is marked PASS.

**Interpretation boundary:** this is a deterministic demonstration that a particular sequential carryover confound can be exposed by clean-baseline runs and an evidence batch. It is not proof of universal superiority over A/B testing, and it says nothing about Critical Thinking skill efficacy.

## Longer-term direction: historical evidence and retrospective analysis

This is a future direction, not work to implement as part of the current method demonstration.

Q-Batch evidence should remain useful after its original experiment has finished. In addition to comparing conditions for one experiment, accumulated run evidence may later support longitudinal questions such as:

- How has `main`'s behaviour changed across weeks or months?
- When did a runtime, failure rate, retry pattern, or other observed property begin to drift?
- Does a development branch differ from the current baseline, and how does that difference compare with the longer-term history?
- Is a change consistent with ordinary run-to-run variability, or does it warrant investigation?
- Can old evidence answer a question that nobody thought to ask when those runs were collected?

### Architectural boundary

- The existing event log records observable events and references to evidence. It does not know whether downstream consumers will compare, aggregate, chart, or otherwise analyse those records.
- Preserve original run evidence; do not replace detailed observations with averages or other irreversible summaries.
- Historical analysis belongs in separate post-processing code. Start with Python and the existing JSONL/manifests/artifacts; introduce another dependency or storage format only if a demonstrated need arises.
- Derived reports should identify the source runs and processing method so a finding can be traced back to its evidence.
- Retain historical evidence beyond ordinary short-lived CI artifact windows if it is to serve as a longitudinal baseline. The archive/retention mechanism is a separate future decision.
- Record enough run context to judge comparability, including source commit, test/suite identity, configuration, environment and relevant data/seed identity. Do not assume runs are comparable merely because their test names match.
- Treat trends and correlations as investigative evidence, not automatic proof that a particular commit caused a change.

### Scope boundary

This direction does not require changing the event logger into a comparison system, adopting Allure or another reporting product, adding DuckDB, introducing Parquet, or building a dashboard now. Existing tools may provide reusable mechanisms later, but Q-Batch should borrow individual mechanisms only when they solve a concrete need.

The first practical exploration, when undertaken, should be a small Python post-processor over existing Q-Batch evidence to test a real historical question without modifying the source logs. No historical archive, scheduled baseline run, charting system, or new dependency is being introduced by this plan.



## Context object: implemented foundation

Q-Batch now has a small context catalog and loader under `experiments/ct_ab/`. The catalog currently defines contexts for the Critical Thinking skill pilot, the deterministic order/carryover methodology demonstration, and instrumentation preflight.

Each context records a stable `context_id`, version, summary, description, purpose, rationale, optional hypothesis, origin references, creation date/author, and optional notes. These records explain why evidence is collected; they are not run outcomes or conclusions. Missing hypotheses remain explicitly null rather than being invented.

New runs must embed both `context_id` and an exact context snapshot in `manifest.json`. The logger binds the context ID and canonical snapshot SHA-256 into the first, hash-chained `run_started` event. Validation checks the snapshot against that event and paired-run validation requires the two runs to use the same context identity and snapshot. This detects silent edits to the embedded context without changing the logger into an analysis engine.

The catalog is the source for context used by new runs; the embedded snapshot preserves the explanation that was true for that execution even if the catalog is revised later. Update a context by incrementing its version and preserving the old meaning for historical runs, rather than silently rewriting past explanations. Origin references can point to repository files, issues, discussions, incidents, design decisions, or other records; Git commits alone are not assumed to explain the original motivation.

The context is separate from execution evidence and later interpretation:
- Context says why the test exists and what question it addresses.
- Run evidence records what happened and under which conditions.
- Interpretation records conclusions and should point to source runs and analysis methods.

Compatibility boundary: validation continues to accept older manifests with no context and reports them as `legacy_missing`; the current logger requires context for newly created runs. No new event fields, comparison UUID, dashboard, or external dependency is introduced. A comparison group, if later added, remains separate from context and does not establish that grouped runs are comparable.


### Attempt 4 — invalid: repeated rejected plan submissions

Run [41619488320](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41619488320), commit `ff8339e306ab749f8f154a3580c073385a6f5737`:

- Both A and B submitted a plan successfully, then repeatedly submitted `submit_plan` again.
- The runner correctly rejected each duplicate with `plan may be submitted only once`.
- Each arm recorded 7 rejected duplicate submissions and 24 dispatched tool calls before the runner exhausted its 24-turn budget without calling `finish`.
- This is an observed repeated-action failure. The archive does not, by itself, establish the model's internal reason for repeating the plan.
- A stabilisation correction now stops immediately when this specific existing one-plan contract is violated, records `agent_loop_detected` with reason `duplicate_plan_submission`, and raises an explicit runner error. A deterministic regression test verifies that only two model responses are needed, only one plan is recorded, and the duplicate is logged as failed.

This correction and test are on the draft historical-analysis PR branch; see the current PR and CI record in the stabilisation update below. No real-model rerun has been launched to test the correction.


## Stabilisation verification — 4 November 2026

- Historical archives replayed against the current reader: **4 archives / 8 run logs**.
- Integrity: **8/8** event chains, referenced evidence and final checksums verified; **920** evidence references re-hashed; **0** read failures.
- Classification: the four original attempts retain four distinct signatures. Each has one independent attempt and lacks producer provenance required for a comparable diagnostic cohort. The conclusion remains inconclusive; no rerun is authorised by the evidence.
- Current historical report: `experiments/qbatch_historical_analysis/reports/2026-11-03-ct-ab-failure-cohort.md` and matching JSON.
- Draft PR: [#22](https://github.com/memoryprismv1/ael-runtime-accountability/pull/22), branch `qbatch/historical-cohort-analysis-prototype`.
- Latest recorded CI for this correction: [run #351](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41791081760), commit `740d6ef1e138898302169531c44d77d647ba883b`; Python 3.11, 3.12 and 3.13 jobs all passed.
- Python 3.11 test groups: 65 runtime/generic logger tests, 32 CT logging and paired-runner tests (including the new duplicate-plan regression), 2 order/carryover methodology tests, and 18 historical-analysis tests.
- The PR remains draft and unmerged. The real-model pilot workflow was not triggered.

This record verifies the current reader against historical archives and the minimal duplicate-plan guard. It does not declare either repository production-ready or declare the real-model experiment successful.


## Real-model workflow safety — 4 November 2026

The expensive CT real-model pilot is now **manual-dispatch only**. The workflow no longer has a `push` trigger on `main`; routine merges and stabilisation commits cannot start the Ollama/model download job. A pilot can run only when a person deliberately selects Actions → CT A-B real local-model pilot → Run workflow. This is an execution-safety boundary, not a change to the experiment protocol. No real-model run was started during this stabilisation work.
