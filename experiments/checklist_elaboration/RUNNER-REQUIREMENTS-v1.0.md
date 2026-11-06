# Checklist-elaboration planning runner — requirements v1.0

**Status:** implemented reference. The planning runner is in [AEL PR #29](https://github.com/memoryprismv1/ael-runtime-accountability/pull/29); CI and current execution details are in [IMPLEMENTATION-STATUS-2026-11-06.md](IMPLEMENTATION-STATUS-2026-11-06.md). The private manual-only hosted workflow is `.github/workflows/qbatch-checklist-elaboration.yml` in Differential.  
**Purpose:** support the four-cell MP × CT planning experiment without human intervention or generated-code execution.

## 1. Keep it separate from the existing Kanban runner

Create a new experiment module, for example:

`experiments/checklist_elaboration/`

Do not retrofit the existing Kanban-specific `experiments/ct_ab/agent_loop.py` or alter the previous real-model experiment. The old task, acceptance suite, score packets, and historical logs remain unchanged.

The new runner may reuse the proven Q-Batch `RunLogger`, event schema, hash-chain and artifact-validation code where appropriate, but must have its own:
- generic planning-task prompt;
- planning-only tool allowlist;
- skill-condition loader;
- read-only input workspace;
- write-restricted deliverable workspace;
- run and four-cell block manifests;
- output validator;
- simulated input-request and user-dependency reporting.

## 2. Condition inputs

Run four conditions from the same frozen task fixture:

| Internal cell ID | Full MP Starter-Kit bundle | CT skill bundle |
|---|---|---|
| MP0_CT0 | absent | absent |
| MP1_CT0 | present | absent |
| MP0_CT1 | absent | present |
| MP1_CT1 | present | present |

Assign blind labels A/B/C/D independently within each four-cell block; never use the internal cell ID as the assessor-facing label.

### MP bundle

Check out only at the pinned commit:
- repository `memoryprismv1/memoryprism`
- commit `5cc48df650b1942412047ee6e82642c14e800967`

Provide the complete relevant `skill/` subtree read-only so that the Skill's links resolve, including:
- `skill/SKILL.md`;
- `skill/references/starter-kit.md`;
- Framework source rendering and the four Foundation and three Supplementary essays;
- `skill/references/source-corpus/README.md`.

The MP skill says to consult sources selectively. Do not pre-inject every essay into the system prompt. Let the read-only file tools expose the pinned source material as needed.

### CT bundle

Check out only at:
- repository `memoryprismv1/cognitive-interface-ai-skills`
- commit `8152c98d2e388735d8bf63857b46a2056ef0a967`

Provide:
- `critical-thinking/SKILL.md`;
- its fixed `MEMORY-PRISM-CHECKLIST.md`;
- its `MEMORY-PRISM-REFERENCE.md`.

These are a read-only CT package. The tiny optional MP reference embedded in this CT package is not the full MP Starter-Kit factor. Do not change it, expand it, or make it mandatory.

In cell C, provide the CT package only; do not provide the separate MP Starter-Kit subtree. In cell D, provide both packages. Never infer or synthesise missing skill content.

## 3. Identical baseline prompt

All cells receive the same base system prompt and the same `TASK.md` / `source-pack/` bytes. The only planned changes are the addition or absence of the pinned skill packages.

The base prompt must:
- describe the planning task and three required outputs;
- state that all useful work should be completed autonomously;
- state that no real user or sponsor is available and no message will be sent;
- explain the simulated request_input tool and require the agent to continue after its no-response result;
- instruct the agent to inspect all relevant local source materials before declaring something unavailable;
- distinguish facts, inferences, assumptions and unresolved decisions;
- allow safe bounded assumptions and justified deferrals;
- require independent work to continue while a decision remains open;
- prohibit unsupported expansion beyond the first-terminal pilot;
- require the three output files and factual completion summary.

Do not write a baseline prompt that contains an abbreviated MP or CT checklist. The baseline should be an ordinary, clear task instruction, not a hidden copy of either treatment.

Do not tell the agent to maximise checklist length. The brief and rubric reward material, valid coverage, not verbosity.

## 4. Tool allowlist

This is a planning-only runner. It must not contact a real user or wait for a human response. To measure what information the agent would otherwise request, expose a **simulated input-request tool**. This is a recorder only; it never contacts a person and never supplies an answer.

Minimum tool set:

1. list_files(path) — list allowed task/source/skill files.
2. read_file(path) — read allowed task/source/skill files.
3. write_file(path, content) — write only under deliverables/.
4. request_input(question, why_needed, project_role) — record a hypothetical request for external information or a decision. The runner records the exact arguments and immediately returns a fixed no-response result:
   { "status": "captured_no_contact", "response": null, "instruction": "No human is available in this run. Continue independently; record a genuinely unresolved decision in open-decisions.md and proceed with all work that does not depend on it." }
   It sends no message, does not notify the user, and never waits.
5. finish(summary, known_limitations) — mark the run complete with a factual summary.

No real ask_user, request_clarification, pause-for-human, messaging, email, shell, Python, command execution, browser, network, package installation, arbitrary file access, generated-code execution, database, or external API tool.

Do not include a separate submit_plan tool. The project plan is the deliverable; adding a second planning declaration would create process overhead unrelated to the research question.

### File access rules

- task/ and source-pack/ are read-only.
- MP and CT skill source trees are read-only.
- Evaluator materials, reference coverage map, condition key, scoring rubric, previous run workspaces and other condition outputs are not visible to the agent.
- The only writable path is deliverables/.
- The runner must reject attempts to write or replace anything outside deliverables/, including a path traversal or symlink escape.
- Capture failed write attempts as tool events.

## 5. Logging requirements

Reuse the existing event logger where possible. Preserve enough information to answer what the agent did and what the tools actually returned.

Required observable events include:
- run started/finished;
- condition manifest hash and blind label;
- skill bundles supplied, pinned commit and file hashes (in private raw evidence);
- model request started/succeeded/failed, with request ID and provider usage metadata where available;
- tool calls, arguments, result, status and duration;
- file reads with path, byte size and hash;
- file writes with path, byte size and hash;
- failed writes or unknown tool attempts;
- loop/recovery events;
- resource-limit and timeout events;
- deliverable-validation result;
- final status.

Preserve raw model request/response payloads in the private audit archive only. Do not put condition mapping, skill text, or raw prompts/responses in assessor-facing blinded packets.

Separate agent-declared claims from runner-observed facts. For example, a sentence in `plan.md` that says "all incidents are handled" is not evidence; the actual content and evaluator check are the evidence.

## 6. Simulated input-request and user-dependency capture

The request_input tool is simulated. It records a hypothetical request, then immediately returns no answer. It does not contact the experiment user or any other person.

Capture:
- every request_input call, exact question, stated reason, proposed decision owner, event sequence and whether it is a repeat;
- attempted calls to undefined real ask_user, send_message, request_clarification, or other human-contact tools;
- statements in plan.md, open-decisions.md, or final summary that directly ask the user to supply information, make a choice, do research, or respond before the agent can proceed;
- explicit statements that independent work is blocked pending a human response.

The request tool must never provide a fabricated answer. Its fixed no-response return lets the run continue and lets the evaluator count how often the agent would seek further input.

Do not count as user dependency:
- identifying a future decision that belongs to a named airport role;
- stating that an authorised project role must approve a policy before live activation;
- transparently recording that the evidence does not establish a value.

Use both deterministic detection and human review. Keywords alone are insufficient: distinguish "operations owner must approve the threshold before activation" from "please tell me the threshold before I continue."

A simulated request is not automatically a failure. Score its necessity and handling:
- Was the missing information genuinely absent from the source pack?
- Was the proposed role appropriate?
- Could safe reasoning, source inspection, a bounded assumption, or a justified deferral have avoided the request?
- Did the agent continue useful independent work after receiving no answer?
- Did it repeat a request or block the plan needlessly?

## 7. Loop and stop behaviour

The old Kanban run exhausted 24 turns on repeated plan/tool behaviour. The new runner must fail fast on:
- repeated identical no-tool responses;
- repeated failed tool arguments without a useful change;
- repeated identical request_input calls or attempted real human-contact tools;
- repeated writes that do not change the deliverable;
- tool call limit, model turn limit, or wall-clock limit.

A loop stop is a validly captured incomplete run, not a successful deliverable. Preserve the cause and last useful state.

Do not shorten a skill-enabled run just because it has produced more valid checklist items. Use the same resource ceilings for all four cells.

## 8. Resource instrumentation

Common pilot ceiling:
- 48 model turns per run;
- 120 tool calls per run;
- 600 seconds per individual model request;
- 4,000 generated tokens per run where accurately enforceable;
- 45 minutes hard wall-clock per run.

The four-cell batch workflow must have enough total time for four sequential runs plus setup/validation. If the hosting limit cannot support this, use four isolated jobs with the same per-run ceilings and a pre-registered randomisation/order plan. Do not quietly give one condition a larger budget.

Record provider-reported prompt and completion token counts where available. Record actual elapsed wall-clock and per-request durations. If aggregate token usage cannot be observed, say so in the report.

If a resource ceiling is hit:
- mark the run incomplete/censored;
- retain all existing outputs and logs;
- do not label the run a completed low-quality plan;
- do not extend only that condition after seeing its performance.

## 9. Deliverable validator

At minimum validate:

- `deliverables/plan.md` exists and is non-empty;
- `deliverables/consideration-register.json` parses as JSON and contains a list of items with the required fields;
- `deliverables/open-decisions.md` exists and is non-empty;
- all deliverables are within byte/size limits set before a run;
- source-pack and skill-source files have not changed;
- no write escaped the deliverables directory;
- no real human-contact tool was used; simulated request_input calls are permitted and logged.

The validator checks structure, not truth or quality. The independent scorer applies `SCORING-RUBRIC-v1.0.md` and the hidden reference map.

A run can be instrumentation-valid but task-incomplete. Record instrumentation, completion, resource-stop and scoreability as separate fields.

## 10. Blinding and private evidence

The current AEL repository is public and its existing workflow uploads raw model artifacts publicly. **Do not use that workflow for the new real-model run.**

Before dispatch:
- execute the experiment from a private repository or other verified private runner;
- confirm that raw Actions artifacts, logs, prompts, skill text, manifests and condition key are private;
- store the condition key separately from scorer packets;
- assign blind labels A–D by a random mapping within each four-cell block;
- give assessors only deliverables and an observable, redacted execution trace;
- freeze scores before unblinding;
- keep the full raw logs privately available for audit.

No generated code is executed in this experiment, which removes the previous Kanban execution risk. Privacy of raw model prompts/responses and of the condition mapping is still required.

## 11. Runner test suite before a model run

Add deterministic tests proving:

1. The same task/source bytes and resource configuration are supplied to every cell.
2. MP and CT bundles appear only in their assigned cells and match the pinned commits.
3. The CT-only cell does not receive the full MP Starter-Kit package.
4. The combined cell receives both without rewriting or merging their contents.
5. The only input-request tool is the simulated request_input tool; it records the hypothetical request and immediately returns no answer.
6. Attempts to use real human-contact tools are recorded and stop the run; simulated request_input calls do not stop the run.
7. Only `deliverables/` is writable; source and skill trees cannot be modified.
8. Path traversal and symlink escapes are rejected.
9. Repeated no-tool and repeated failed-tool loops stop with auditable reasons.
10. Turn, tool, output and wall-clock ceilings are applied equally.
11. Resource stops are labelled incomplete/censored, with partial evidence retained.
12. Each condition receives a clean workspace and independent conversation.
13. The evaluator-only reference files cannot be listed or read by the agent.
14. Output validation distinguishes malformed/missing outputs from a completed plan with weak quality.
15. Hash tampering in events/artifacts is detected by the logger validator.

Only after this deterministic preflight passes and private evidence storage is verified should a four-cell real-model feasibility block be dispatched.

## 12. Explicit non-goals

This implementation must not:
- modify the original Kanban task or its historical records;
- add a live user-interaction workflow; the simulated request_input tool is only an experiment measurement instrument;
- expand the skills themselves;
- rewrite the MP or CT checklist to suit the benchmark;
- run code generated by the agent;
- implement a dashboard or database;
- claim general efficacy from the four-run feasibility block;
- auto-dispatch real-model runs on PRs or ordinary commits.
