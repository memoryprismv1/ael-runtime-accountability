# CT A/B Experiment Logging Gate

This package provides a shared JSONL logger, a versioned event contract, artifact integrity checks, and paired-run validation. Both conditions use the same code and schema; the model does not supply or modify the logger.

> **Scope correction:** the heavyweight real-model skill-on/skill-off pilot is not the test of whether Q-Batch is useful. It is an attempted application experiment that has so far failed in both conditions before producing a valid pair: earlier runs hit tool-protocol/no-tool loops, and a later run timed out on the first model request. Those failures show that this task/model/runner combination is too expensive or brittle for a useful first test; they do not show that Q-Batch failed, that A/B is inherently inferior, or that the skill helps or hurts. A later attempt also exposed repeated resubmission of an already accepted plan; this is a runner-control failure path, not efficacy evidence. Test Q-Batch's evidence workflow with small, deterministic, inexpensive fixtures first. Keep real-model efficacy testing separate.

## Layout

- experiments/ct_ab/log_schema.schema.json — versioned JSON Schema for a single event.
- logger.py — runner-owned JSONL logger, command and tool-call capture, raw model request/response capture, file snapshots, artifacts, checksums, and hash chaining.
- validate_log.py — validates manifest, event fields and order, per-event hash chain, checksum, and referenced artifacts; the pair validator compares controlled manifest fields and required event types.
- preflight.py — creates two synthetic, unscored rehearsal runs and emits preflight-report.json.
- test_logging.py — positive and negative tests, including tampered events/artifacts, control mismatches, and workspace/log path separation.

Use from the repository root:

    python -m unittest experiments.ct_ab.test_logging -v
    python -m experiments.ct_ab.preflight --output /path/outside/workspaces/ct-ab-rehearsal
    python -m experiments.ct_ab.validate_log /path/to/run-a

The output directory must be new or empty. Each RunLogger writes to a run directory disjoint from the agent workspace and refuses to overwrite a non-empty run. It opens events.jsonl exclusively, appends one event per line, flushes/fsyncs every event and chains event hashes. Captured artifacts are stored by the runner beside the log, referenced by relative path, byte size and SHA-256. checksums.sha256 records the final event-stream hash.

## Event distinction

- Observed: runner/runtime events such as command exit codes, workspace snapshots, test results, and captured tool/model transport events.
- Declared: an agent-submitted plan or concise note. Those are preserved as statements, not treated as proof that an action occurred.
- Captured command stdout/stderr are artifacts; the log never treats a model saying “tests passed” as the test result.
- No hidden chain-of-thought is requested or stored. Only submitted plans and short declared explanations of decisions are captured.

## Run manifest and blinding

Each manifest contains the blind condition label (A or B), task brief hash, a hash of the complete condition configuration (without exposing the skill mapping), schema/logger versions, model identity/version, environment, resource limits and starting commit. The skill-on/off mapping remains in a separate controller-owned file outside both workspaces. The rehearsal uses explicit REHEARSAL-A/B labels and a synthetic model identity. **Repository visibility still governs evidence visibility:** raw audit artifacts can reveal the enabled condition, and the public repository makes those artifacts available to repo readers.

For scored runs, both conditions must start from clean copies of the same baseline, use the same client brief and tool/resource policy, and send all runner-observable commands and file changes through the shared runner. The controller must route tool dispatch through record_tool_call and use record_model_exchange at the actual model transport boundary to preserve the prompt/response and provider-reported usage metadata. If the chosen runtime cannot expose raw requests, responses, or token usage, record that as unavailable rather than infer it. A condition that bypasses instrumentation is not valid.

## Preflight gate

Do not begin scored runs until all are true:

1. Unit tests pass.
2. The rehearsal produces two valid completed logs and the machine-readable preflight report says PASS.
3. Both logs include planning, synthetic-model request/response capture, tool-call capture, command start/finish, file changes, test result, captured artifacts, failure and recovery events.
4. The pair validator confirms controlled manifest fields match and verifies all evidence hashes.
5. Tampering with an event, referenced artifact, or controlled manifest field causes validation failure.
6. Logger output is outside and disjoint from the agent workspace.

A successful preflight establishes only that instrumentation functions as intended. It does not establish that a model or the Critical Thinking skill improves software or reasoning. Synthetic rehearsal events are never scored.

## Known limits

Hash chains detect accidental edits and unsynchronised tampering; they are not a cryptographic guarantee against an administrator who can rewrite the entire log and recompute all hashes. Keep the runner and run output under a separate owner/process where possible, preserve a final signed/remote checksum in a controller-owned location, and record instrumentation failures. A process log cannot infer hidden internal cognition and deliberately does not attempt to do so. A full future runner must be the enforcement point for shell/editor/file access; the command helper is a capture implementation, not a sandbox by itself.


## Client-task runner and paired skill comparison

The instrumentation gate is now paired with a fixed, Trello-inspired Kanban client task and an independent post-run acceptance suite. The agent workspace receives the client brief and API contract through its prompt; it does not receive the acceptance test source.

### Local model inventory

    python -m experiments.ct_ab.paired_runner doctor

This contacts only a local loopback Ollama service, lists exact installed model names, and does not prompt a model.

### Before a scored pair

The exact Critical Thinking skill file must be supplied from its real source. The runner hashes it, injects its bytes into only the enabled condition, and keeps the condition key outside the blinded output bundle. It does not invent or substitute a skill file.

    python -m experiments.ct_ab.paired_runner run-pair --output /path/to/new-pair-output --model EXACT_NAME_FROM_OLLAMA_LIST --ct-skill /path/to/the/actual/Critical-Thinking-SKILL.md --allow-host-execution

Use a new, empty output directory. Both blind runs use the same model, options, brief, workspace starter, tool definitions and resource limits. The run order and mapping of A/B to skill-off/skill-on are randomized; the controller key is written to a separate sibling location by default. Do not provide that key to blind scorers until their scores are frozen.

The output has two source bundles, two structured event streams, raw request/response evidence, independent acceptance reports, a blinded pair report, checksums, and a task manifest that hashes the brief, API contract, starter and acceptance suite.

### Execution safety and interpretation

**Host execution requires explicit opt-in.** The acceptance runner starts model-generated app.py as the current OS user. It is not an OS sandbox. Run this only in a disposable VM/container with no secrets, personal data or valuable files accessible. The tool interface prevents arbitrary shell calls from the agent, but that alone does not make its code safe to execute.

The --allow-host-execution option acknowledges this limitation; it does not create a sandbox. An installed local model and the exact real skill file are prerequisites for scored runs. Mock-model CI exercises the harness only; it is not the real experiment and cannot show the skill improves reasoning.


### Blind assessor packets

After each run, the controller produces score-packets/score-A.zip and score-packets/score-B.zip. Each packet includes the source code, client task hashes, fixed acceptance report, plan, final summary, a redacted timeline of observable work, the same scoring rubric, a JSON scorecard schema, and a blank scorecard template. Raw model prompts/responses, condition configuration hashes and the separate condition key are omitted from the scoring packet.

Have assessors score A and B independently before comparing or opening the key. Preserve original scorecards and disagreements. The runner records each score-packet SHA-256 in the blinded pair report so reviewers can confirm the packet has not changed. The acceptance score remains a separate, objective task result; human ratings add qualitative assessment but do not replace it.

### Multi-assessor scorecards and reports

New packets include a v2.0 `scorecard-template.json` with an `assessments` array. Add one independent assessment object per assessor; do not combine ratings or reuse an assessor ID within the same blind response. Each packet's `case_id` is the exact task-bundle SHA-256, so repeated pairs for the same task can be grouped without inventing a case label. Dimension applicability is explicit: applicable dimensions require a 1–5 score and evidence; not-applicable dimensions require a null score and a rationale.

The original v1.0 schema is included as `scorecard-v1.schema.json`, and existing single-assessor v1.0 scorecards remain readable. Because v1.0 has no case identifier, its reports use a clearly marked legacy placeholder scoped to the existing pair ID; unrelated old pairs are not silently grouped as one case. The validator/report tool uses only the Python standard library:

```bash
python -m experiments.ct_ab.scorecards validate scorecard-A.json scorecard-B.json
python -m experiments.ct_ab.scorecards report scorecards/ --out scorecard-report.json
python -m unittest experiments.ct_ab.test_scorecards -v
```

For directory input, the tool reads `scorecard-*.json` files and ignores the blank `scorecard-template.json` and bundled schema files. Reports show descriptive score counts, ranges, means/medians, not-applicable counts and observed disagreement by blind label, case and dimension. Score the dimension ratings independently on each packet first; after both are frozen, record the same pair-level preference in that assessor's entry on both A and B scorecards. Do not change dimension ratings to force agreement. Pair preferences are counted once per assessor only when repeated A/B entries agree; incomplete and conflicting submissions are surfaced. Reports never map blind labels to skill-on/skill-off, and they do not treat agreement as proof of correctness or rating spread as a significance test.


### Pinned real skill and one-click local-model pilot

The A/B runner pins the input skill to commit d1f23e2ad9dafd323940fc6b7a00f1700275d885 in memoryprismv1/cognitive-interface-ai-skills, file critical-thinking/SKILL.md. It verifies the Git blob SHA-1 for exact bytes and records the file's SHA-256. A different revision is refused, not silently accepted. The pin lives in skill_source.json.

A GitHub Actions workflow is provided at .github/workflows/ct-ab-real-model-pilot.yml. **The real-model pilot is manual-dispatch only.** Routine pushes, PR updates, and merges do not launch it. To deliberately start the pilot, use Actions → CT A-B real local-model pilot → Run workflow. The workflow installs Ollama on an ephemeral GitHub-hosted Linux VM, downloads the fixed local model qwen2.5-coder:7b, verifies the exact skill revision, then runs both conditions with the same settings. The model page describes Qwen2.5-Coder as a code-focused family and lists its 7B variant as 4.7 GB. See the [official Ollama model page](https://ollama.com/library/qwen2.5-coder).

**Public-repository limitation:** this repository is public, and the `ct-ab-audit-evidence` Actions artifact contains actual model requests/responses and can reveal the enabled condition. Anyone with repository read access can access public Actions artifacts. Therefore the audit artifact is not private from assessors or other repo readers, and this workflow cannot provide confidential blind scoring in its current public-repository configuration. Do not use this public workflow for sensitive inputs or claim the blind condition is secret. A future blinded efficacy pilot requires a private evidence destination or restricted repository before it is run. The workflow is manual-dispatch only; no model run is part of routine CI.

The CI model run executes generated application code on a disposable hosted VM, not inside a hardened sandbox. Credentials are not persisted by checkout, the acceptance subprocess receives a restricted environment, and the source app has no project secrets. This limits exposure but is not a security guarantee against arbitrary code. The workflow is isolated from routine regression CI, so ordinary test changes do not unexpectedly download a multi-gigabyte model or consume a long CPU run.

The model-run artifact is a real local-inference pilot, not the mock-model test. One pair remains exploratory and does not establish general CT efficacy.


### First real-pilot result and recovery

The first real-model attempt (run 39592787189) did not produce a valid comparison. Both Qwen2.5-Coder conditions emitted calls as JSON in the response content, sometimes inside a JSON code fence, instead of Ollama's structured tool_calls field. The runner never dispatched tools, each condition exhausted its 24-turn budget, and the independent acceptance suite was correctly not run. This is a tool-protocol compatibility failure, not evidence for or against the Critical Thinking skill.

Ticket #7 adds a deliberately narrow fallback: it accepts only one complete allowlisted {"name":...,"arguments":{...}} object, either raw or inside a single JSON code fence. It refuses arbitrary prose, unknown tool names, malformed JSON, non-object arguments, and extra fields. The raw response remains in audit evidence while the normalized call is what enters subsequent conversation history.

The parser fix no longer has any automatic real-model workflow side effect. The pilot can be started only through an explicit manual dispatch. A valid attempt needs both runs to finish, produce observed tool/file/test events, pass the log validator, and generate independent acceptance reports. Until then, no skill-effectiveness claim is warranted.


### Second real-pilot result: no-tool repetition loop

The follow-up pilot (run 39597455540) passed pinned-skill verification and Ollama preflight but again did not produce a valid comparison. The model then repeatedly returned prose or echoed prior tool output without invoking a tool; both runs exhausted their 24-turn budgets. Acceptance was not run. This is a runner/model interaction failure, not evidence for or against the skill.

Issue #8 adds an explicit recovery prompt, hash-based repeated-response detection, a bounded consecutive no-tool limit, and structured `agent_recovery_attempt` / `agent_loop_detected` events. The runner must stop with an auditable reason rather than spend the rest of the inference budget repeating the same instruction.



### Fourth real-pilot attempt: duplicate plan resubmission

Run [41619488320](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41619488320) failed to produce a valid pair. Both conditions submitted a plan successfully, then repeatedly called `submit_plan` again. The runner rejected each duplicate under the existing one-plan contract. Each arm recorded seven rejected repeat submissions and 24 dispatched tool calls before the 24-turn budget expired without a successful `finish`.

This establishes an observed repeated-action failure, not the model's internal reason for repeating itself.

**Stabilisation correction:** the runner now stops immediately after this exact duplicate-plan rejection, emits `agent_loop_detected` with reason `duplicate_plan_submission`, and returns an explicit runner error. The deterministic regression test verifies that the second model response is the stopping point, only one `plan_submitted` event is recorded, and the failed duplicate tool call remains in the audit log. This correction was merged to `main` in commit `b87cb320cc53e59357fd334fbdd8b46fab899a2f`; the post-merge routine CI passed across Python 3.11, 3.12 and 3.13 in [run #362](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41794072403).

No real-model rerun has been launched to test the correction. That is deliberate: routine CI is sufficient to verify the existing one-plan contract without another expensive model run.


## Separate question: what Q-Batch is meant to demonstrate

Q-Batch is an evidence-batching and comparison workflow, not a claim that every A/B experiment should be replaced. The practical question here is whether it makes tests possible to inspect and compare when the ordinary back-to-back experiment is too costly, fragile, stateful, or difficult to reproduce.

The current real-model pilot does **not** answer that question: both conditions have been too heavy for the available execution setup, and neither produced a valid scored pair. Do not keep spending multi-gigabyte downloads and long model runs just to test whether the logger records evidence correctly.

The next methodological test should be a cheap, deterministic fixture with known expected outcomes. It should:
1. Demonstrate a specific failure mode in a naive sequential comparison (for example, a shared mutable state that makes the second result depend on which condition ran first).
2. Run the same conditions independently from a declared clean baseline.
3. Record condition, order, baseline/state identifiers or hashes, outcomes, and failure/skip status in the evidence batch.
4. Verify that the batch report exposes the order-dependent result and that clean-baseline results are comparable.
5. Label this a **synthetic methodology demonstration**, not real-model efficacy evidence.

A fixture that merely proves JSONL hashes validate is a logger test. A fixture that deliberately creates and then detects a known order/carryover confound is a Q-Batch methodology test. Keep those claims separate.


## Run the deterministic method demonstration (no model required)

Run this from the repository root:

    python -m unittest experiments.ct_ab.test_method_demo -v
    python -m experiments.ct_ab.method_demo --output /path/to/new-method-demo

The command creates six immutable run logs: sequential A→B, sequential B→A, and isolated clean-baseline A/B. The fixture deliberately leaves state behind after the first sequential condition. It checks that reversing the order changes which condition appears to have the clean result, while isolated conditions both start clean. Every run is validated, and `method-report.json` records the result and limitations. The output directory must be new or empty.

This is a synthetic demonstration of one known carryover failure mode. It does not use Ollama, call a model, execute generated application code, or establish model/skill efficacy. CI runs it separately from the heavyweight real-model pilot and uploads its evidence artifact.

## Future direction: longitudinal evidence (planned, not implemented)

Q-Batch may later retain historical test-run evidence so that it can be queried across time, not only compared within one experiment. For example, weekly runs of `main` could form a historical baseline against which development branches are compared, while the same archive supports retrospective investigation of drift or recurring failure patterns.

This is a future direction; it is not part of the current logger or method demonstration.

Design boundaries:

- The event logger records what happened and preserves evidence. It does not implement comparisons, charts, aggregation, or downstream analysis.
- Keep original run evidence available. Do not retain only averages or other lossy summaries that prevent later analysis of distributions and individual observations.
- Implement future analysis as separate post-processing. Python over the existing JSONL files, manifests, and artifacts is the starting point; no new analytical dependency is currently required.
- Keep derived findings traceable to their source runs and processing method.
- Longitudinal use will require an evidence-retention mechanism beyond the short retention window of ordinary CI artifacts. That mechanism is not selected or implemented yet.
- Comparisons must account for commit, test-suite/configuration and environment differences. Historical correlation alone does not prove causation.

We may borrow individual mechanisms from existing tools when useful, but we are not adopting a reporting product or building a dashboard now. The next exploratory step, when prioritised, is to test a concrete historical query with a small Python processor against existing Q-Batch evidence without changing the source logs.



## Test context: implemented foundation

New runs now carry a durable explanation of why their test exists. The source catalog is `context_catalog.json`, the context schema is `context_schema.schema.json`, and `context.py` loads and validates catalog entries. Three initial records cover the real skill-on/off pilot, the deterministic order/carryover method demonstration, and instrumentation preflight.

A context record contains:
- stable `context_id` and integer `version`;
- `summary`, `description`, `purpose`, and `rationale`;
- optional `hypothesis` (null when none is recorded);
- `origin_refs` to repository files or other relevant source records;
- `created_at`, `created_by`, and optional notes.

The producer is not fixed: a human, agent, runner, or later process may maintain the catalog. Missing rationale must not be invented just to fill a field.

Every newly created run manifest embeds `context_id` plus the full context snapshot. The logger writes the context ID and SHA-256 of the canonical snapshot into the first `run_started` event, binding the snapshot to the event hash chain. The validator checks this binding, and paired-run validation rejects runs whose context identities or snapshots differ. This makes silent manifest-only edits to context detectable.

The catalog provides current definitions; the manifest snapshot preserves the exact explanation associated with each run. When a context changes, increment its version and preserve the old version's meaning for historical evidence. Do not edit old manifests to match the latest catalog. Context is separate from execution evidence and later interpretation.

Older manifests without context remain readable and are reported with `context_status: legacy_missing`; new `RunLogger` executions require a valid context snapshot.

New CT A/B runs also carry explicit producer provenance:
- `capture_profile`: stable profile ID/version plus the capabilities supported by this runner/logger implementation;
- `capture_profile_sha256`: hash of that canonical profile definition;
- `runner_implementation_revision`: checked-out Git commit when available;
- `runner_worktree_clean`: whether the source worktree had no tracked or untracked changes at run creation.

The profile and runner values are copied into the first `run_started` event, so changing or removing the manifest fields alone is detectable. The validator checks the binding and requires the same provenance across A/B. If Git metadata is unavailable, revision/cleanliness are recorded as null; the run remains inspectable but cannot qualify for a fully comparable historical cohort. The capture profile describes supported capture capabilities, not proof that every capability was exercised in a particular run. When those capabilities change, update the profile version and preserve the old definition for historical interpretation.

Old manifests with no provenance remain readable; their absent metadata is not backfilled or inferred. New runs use explicit provenance, while the event schema remains unchanged. This is a provenance improvement only: the event logger still records what happened and does not perform comparisons or analysis. A comparison UUID, if added later, is a separate grouping relationship, not a substitute for context.
