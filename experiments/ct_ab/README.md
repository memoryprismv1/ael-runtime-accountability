# CT A/B Experiment Logging Gate

This package must be implemented and rehearsed before the scored Critical Thinking skill-on/skill-off software task begins. It provides one shared JSONL logger, one versioned event contract, artifact integrity checks, and paired-run validation. Both conditions use this same code and schema; the model does not supply or modify the logger.

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

Each manifest contains the blind condition label (A or B), task brief hash, a hash of the complete condition configuration (without exposing the skill mapping), schema/logger versions, model identity/version, environment, resource limits and starting commit. The skill-on/off mapping must remain in a separate controller-owned file not available in either workspace or to blind assessors until scoring is frozen. The rehearsal uses explicit REHEARSAL-A/B labels and a synthetic model identity.

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


### Pinned real skill and one-click local-model pilot

The A/B runner pins the input skill to commit d1f23e2ad9dafd323940fc6b7a00f1700275d885 in memoryprismv1/cognitive-interface-ai-skills, file critical-thinking/SKILL.md. It verifies the Git blob SHA-1 for exact bytes and records the file's SHA-256. A different revision is refused, not silently accepted. The pin lives in skill_source.json.

A GitHub Actions workflow is provided at .github/workflows/ct-ab-real-model-pilot.yml. **Merging this PR automatically starts the pilot**: the workflow is triggered by a push to main that changes the workflow file itself. It installs Ollama on an ephemeral GitHub-hosted Linux VM, downloads the fixed local model qwen2.5-coder:7b, verifies the exact skill revision, then runs both conditions with the same settings. The model page describes Qwen2.5-Coder as a code-focused family and lists its 7B variant as 4.7 GB. See the [official Ollama model page](https://ollama.com/library/qwen2.5-coder). The same workflow can be rerun manually from Actions → CT A-B real local-model pilot → Run workflow.

Download **ct-ab-blind-score-packets** for blind assessment only. Keep **ct-ab-audit-evidence** away from assessors until their scorecards are frozen; those logs contain the actual model requests and so can reveal the condition. The controller key remains outside uploaded artifact paths. The skill/condition can be recovered from the enabled run's manifest and request trace only after scoring has been frozen.

The CI model run executes generated application code on a disposable hosted VM, not inside a hardened sandbox. Credentials are not persisted by checkout, the acceptance subprocess receives a restricted environment, and the source app has no project secrets. This limits exposure but is not a security guarantee against arbitrary code. The workflow is isolated from routine regression CI, so ordinary test changes do not unexpectedly download a multi-gigabyte model or consume a long CPU run.

The model-run artifact is a real local-inference pilot, not the mock-model test. One pair remains exploratory and does not establish general CT efficacy.


### First real-pilot result and recovery

The first real-model attempt (run 39592787189) did not produce a valid comparison. Both Qwen2.5-Coder conditions emitted calls as JSON in the response content, sometimes inside a JSON code fence, instead of Ollama's structured tool_calls field. The runner never dispatched tools, each condition exhausted its 24-turn budget, and the independent acceptance suite was correctly not run. This is a tool-protocol compatibility failure, not evidence for or against the Critical Thinking skill.

Ticket #7 adds a deliberately narrow fallback: it accepts only one complete allowlisted {"name":...,"arguments":{...}} object, either raw or inside a single JSON code fence. It refuses arbitrary prose, unknown tool names, malformed JSON, non-object arguments, and extra fields. The raw response remains in audit evidence while the normalized call is what enters subsequent conversation history.

Merging the parser fix automatically retriggers the real-model pilot. A valid attempt needs both runs to finish, produce observed tool/file/test events, pass the log validator, and generate independent acceptance reports. Until then, no skill-effectiveness claim is warranted.
