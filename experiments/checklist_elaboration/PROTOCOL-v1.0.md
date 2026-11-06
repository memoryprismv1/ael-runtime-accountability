# Q-Batch checklist-elaboration experiment — protocol v1.0

**Status:** design specification; not yet implemented or run.  
**Date:** 6 November 2026.  
**Task fixture:** `task-v1/` in this folder.  
**Experiment type:** exploratory 2×2 factorial comparison of Memory Prism and Critical Thinking as separate skill factors.  
**Execution mode:** autonomous, planning-only; no live user interaction; simulated input requests only; no generated-code execution.

## 1. The question

Memory Prism (MP) and Critical Thinking (CT) make a wider arena of considerations available to an agent. A wider arena may expose more relevant dependencies, constraints, states, evidence gaps, operational risks, alternatives, and decisions. Some of those newly visible items may require information the agent does not have.

The experiment asks:

**Can an agent use the wider consideration space to produce a more complete and reliable plan while absorbing as much of the additional work as possible itself, rather than turning newly discovered gaps into homework for the user?**

This is not a test of whether a longer answer is better, whether the agent can list more checklist items, or whether the skills improve hidden reasoning. Only observable outputs, tool use, evidence, and resource costs are scored.

## 2. Separate the two factors

Do not treat MP and CT as one combined intervention. Test them independently and together.

| Internal cell ID | Memory Prism Starter-Kit factor | Critical Thinking factor | Condition |
|---|---|---|---|
| MP0_CT0 | Off | Off | Ordinary planning baseline |
| MP1_CT0 | On | Off | MP only |
| MP0_CT1 | Off | On | CT only |
| MP1_CT1 | On | On | MP + CT |

Assign assessor-facing blind labels A/B/C/D randomly within each four-cell block, independently of these cell IDs. Keep the mapping in the private condition key only.

The MP factor is the **full Memory Prism Starter-Kit skill**, not the tiny, fixed, optional one-question Memory Prism reference embedded in the CT package.

The CT package contains a small optional MP reference and explicitly keeps it separate from the full MP skill. That small reference remains part of CT in cells C and D. It must not be expanded or treated as the MP factor. In cell C, the full MP Starter-Kit is unavailable; in cell D, it is provided separately.

Do not change, rewrite, combine, or abridge either skill to make the conditions appear more similar. The only planned difference between cells is which pinned skill packages are made available.

## 3. Pinned source versions

Use immutable commits and verify the Git blob for every injected skill file. Never use an unpinned moving `main` reference during a run.

### Memory Prism package

- Repository: `memoryprismv1/memoryprism`
- Commit: `5cc48df650b1942412047ee6e82642c14e800967`
- Skill: `skill/SKILL.md`
- Skill Git blob: `8208fdfb794a2cf78c2b1a310912eddfc2dc80a5`
- Starter checklist: `skill/references/starter-kit.md`
- Starter checklist Git blob: `07c6594a41ce05f7d06b14c59770d78775983520`
- Framework and the seven supporting essays are available at this same commit as read-only reference material. They should be opened selectively when relevant, as the MP skill itself instructs; do not inject all source texts into every prompt.

### Critical Thinking package

- Repository: `memoryprismv1/cognitive-interface-ai-skills`
- Commit: `8152c98d2e388735d8bf63857b46a2056ef0a967`
- Skill: `critical-thinking/SKILL.md`
- Skill Git blob: `0bd33321e535d9e68469307f2128cf27637046c9`
- Its fixed optional MP checklist and reference card are part of the CT package at this commit. They remain tiny, read-only, and optional.

### Q-Batch harness baseline

- Repository: `memoryprismv1/ael-runtime-accountability`
- Baseline commit: `844c61c247f604ad0ec4a0b3e8b6f65844849807`
- Current CT A/B harness and logger are design references only. The existing Kanban-specific runner is **not** the runner for this study. A separate planning-task runner is required.

Before each run, record the full commit IDs, Git blob IDs, actual SHA-256 of supplied skill bytes, model name/digest, task fixture hash, runner commit, logger/schema version, and execution environment.

## 4. Task selection

Use the self-contained synthetic baggage-transfer coordination planning task in `task-v1/`.

It has a fixed purpose and scope: plan a small staff-facing pilot using existing baggage and flight information feeds. It includes source-system inventory, known data-quality problems, example incidents, authority boundaries, and explicitly unresolved operating policies.

This task is suitable because a useful plan must distinguish, among other things:

- source event time from time the coordination layer receives an event;
- duplicate records from new physical events;
- late and out-of-order records;
- missing observations from proof that a bag has not moved;
- conflicting records from resolved facts;
- operational recommendations from authority to make physical or flight decisions;
- the coordination layer from the existing systems of record;
- fixed requirements from derived requirements, assumptions, and decisions that remain open.

The scenario and all records are synthetic. It is not an airport safety assessment or a recommendation for real operations.

### Why planning-only first

Do not ask the agent to implement software in this first experiment. Code execution, acceptance failures, dependency installation, and model tool-protocol issues would obscure the question about checklist elaboration. Planning-only outputs let us compare the consideration space and its cost directly.

A later implementation experiment can follow only after this planning test and its scoring process are stable.

## 5. Autonomy rule — no real homework handoff

All four conditions receive the exact same task brief and source pack. The task includes a simulated input-request tool in all four conditions.

**The actual user is not an information source, reviewer, decision oracle, or runtime dependency in this experiment. No question is sent to a person.**

The runner provides a `request_input` simulation tool. It is a measuring instrument, not a communication channel:
- the agent may use it to record a question it would otherwise put to a project sponsor or authorised role;
- the tool stores the request in the private run log and immediately returns `no_response_available`;
- it contacts nobody, sends no message, waits for no reply, and supplies no answer;
- the returned result instructs the agent to continue independently and record a genuine unresolved decision in `open-decisions.md`;
- repeated requests remain measurable and are not answered.

This preserves the behaviour we need to observe: whether a larger consideration space makes the agent seek additional information, and whether those requests are avoidable, useful, or genuinely necessary. It does **not** turn the experiment user into a source of answers.

The agent must not:
- try to contact a real person or wait for a response;
- assign research or obvious source inspection to the user;
- make completion conditional on an answer when the item can be investigated, inferred cautiously, handled by a reversible assumption, or safely deferred.

The agent must instead:

1. Inspect the entire supplied source pack before declaring that information is unavailable.
2. Search the supplied materials for the answer and preserve the source pointer.
3. Derive consequences from the fixed requirements and evidence, labelling inference as inference.
4. Use a bounded, reversible assumption only where a safe provisional choice is possible. State the assumption and what would invalidate it.
5. Use the simulated `request_input` tool only when an unavailable input would genuinely be requested from an external project role. Do not use it for information present in the source pack or for decisions that can safely be deferred. No human will respond.
6. Defer genuinely unavailable decisions, identify the responsible *project role* (for example, operations owner or data-owning airline), explain why it cannot be decided from the evidence, state what work can proceed meanwhile, and define the gate before the affected feature is activated.
7. Continue all independent work. An open decision or unanswered simulated request is not a reason to abandon the plan.

The final plan may identify decisions that the eventual airport project owner or an authorised operations role must make. That is not an interaction with the experiment user. It becomes a failure when the agent transfers investigatory work, ordinary reasoning, or avoidable choices to the user, or blocks unrelated progress awaiting an answer.

## 6. Required outputs

Every run must produce exactly these three deliverables in its writable output directory:

### A. `plan.md`

An actionable pilot plan: purpose and boundary, architecture and information flow, staff workflow, delivery sequence, verification approach, risks and operational safeguards. It should be concise and internally consistent.

### B. `consideration-register.json`

A structured record of the fixed requirements and additional considerations the agent believes matter. Each item must include:

- stable item ID;
- concise statement;
- category (data, state, timing, authority, workflow, security/privacy, resilience, auditability, evaluation, scope, or other);
- source type (fixed requirement, source fact, derived consideration, assumption, or unresolved decision);
- source/evidence pointer, or an explicit statement that it is derived;
- why it matters to the pilot;
- disposition (resolved from evidence, derived and addressed, bounded assumption, deferred decision, out of scope, or not applicable);
- what the agent did about it;
- whether it changes architecture, sequence, control, test, or scope.

Duplicate restatements do not count as new considerations.

### C. `open-decisions.md`

Only items that genuinely remain unresolved after inspecting the source pack. For each, state the decision, why the supplied evidence cannot settle it, responsible project role, safe interim treatment, what work can proceed, and the activation/release gate.

If there are no unresolved items, state that explicitly and explain how this was established. Do not manufacture decisions to fill a template.

## 7. Run controls

Within each block, hold constant:

- exact task and source-pack bytes;
- exact model name and model digest;
- system prompt except for the two skill factors;
- tool definitions and file-access permissions;
- context window, generation settings and sampling options;
- per-run model-turn, tool-call, output-token, and wall-clock ceilings;
- runner, logger and event schema versions;
- operating environment and available CPU/memory;
- scoring procedure and blind labels.

Each run gets a new, clean workspace and a new model conversation. No run can read another condition's output. Run order is randomised within each four-cell block. Do not share workspace, files, caches that contain conversation state, or intermediate outputs between conditions.

The runner must instrument actual request/response boundaries and preserve exact model usage metadata when the provider exposes it. If a usage field is unavailable, record it as unavailable; do not estimate it and present the estimate as actual usage.

### Resource ceiling for the pilot

Start with a common ceiling of:

- 48 model turns per run;
- 120 tool calls per run;
- 600 seconds per model request;
- 4,000 generated tokens per run, where the runtime can enforce and report this accurately;
- 45 minutes hard wall-clock per run.

These are ceilings, not targets. They replace the old 24-turn limit, which is known to censor the previous run before useful work can complete. Do not increase a ceiling for one cell after seeing its output. If the provider cannot enforce an aggregate output-token ceiling, record that limitation and preserve actual per-request usage where available.

A resource-limit stop is recorded as a censored/incomplete run. Report it separately from a completed low-quality plan. Do not automatically classify a run that uses more resources as worse if its added work is valid; show quality and cost side by side.

## 8. What counts as checklist elaboration

An item counts as a **valid additional consideration** only when it is:

- relevant to the fixed task and pilot boundary;
- not merely a duplicate or rewording of another item;
- supported by a source fact, a sound inference from the supplied constraints, or a clearly labelled decision/assumption;
- capable of changing a design choice, control, operational step, test, risk treatment, or decision gate.

Do not reward:
- more rows or longer prose by themselves;
- generic statements such as "consider security" without a task-specific consequence;
- invented policies, invented thresholds, or unsupported facts presented as settled;
- exhaustive terminology that changes nothing;
- requirements outside the pilot's authorised scope;
- repeating the same point under several MP or CT labels.

A shorter plan with higher coverage and fewer unsupported additions can outperform a longer one.

## 9. Primary outcomes and scoring dimensions

The primary result is a **two-sided profile**, not one composite score:

1. **Useful checklist expansion:** valid additional consideration count, reference coverage recall, and precision.
2. **Additional input demand:** distinct simulated external-input requests, classified as avoidable or legitimate, plus whether the agent treated any as blocking.

For each run, also report the input-demand rate (distinct simulated requests per valid additional consideration) when the denominator is non-zero. Show raw counts beside the rate; do not use the rate by itself when there are few considerations or few requests.

Secondary outcomes are autonomous resolution rate, justified deferral quality, unsupported assumptions, user-directed homework, plan quality, completion status, and resource consumption. Keep all of these separate. A skill could increase coverage and input demand at the same time; the experiment must show both rather than conceal the trade-off in an overall score.

Score separately; do not collapse everything into one headline number.

1. **Base-task completion:** are all fixed requirements handled in the plan?
2. **Valid additional coverage:** how many material considerations outside the literal brief are correctly identified?
3. **Coverage recall:** what proportion of the evaluator's reference considerations were identified and handled?
4. **Precision / overreach:** what proportion of surfaced additions are valid and in scope? How many unsupported or unnecessary items are introduced?
5. **Evidence discipline:** are facts, inferences, assumptions, and unknowns distinguished and traceable?
6. **Autonomous resolution:** how much of the expanded work is actually investigated and addressed using the source pack or sound bounded reasoning?
7. **Deferral quality:** are genuinely unavailable decisions isolated, assigned to the right project role, safely contained, and prevented from blocking independent work?
8. **Simulated input demand:** how often does the agent record an external information/decision request, and how many of those are avoidable? Separately count any direct homework or blocking request addressed to the actual user.
9. **Plan coherence and implementation readiness:** do the discovered considerations materially affect architecture, sequence, workflow, risk controls, and verification?
10. **Resource cost:** turns, tool calls, input/output tokens when supplied, wall-clock time, and any resource-limit stop.

The exact rubric and counting rules live in `SCORING-RUBRIC-v1.0.md`. Simulated request events and explicit user-directed requests in the deliverables are counted separately. Evaluator-only reference considerations must remain outside the agent's workspace.

## 10. Analysis

This is a 2×2 factorial design.

Report:
- MP effect: average difference between cells with MP on and cells with MP off;
- CT effect: average difference between cells with CT on and cells with CT off;
- MP×CT interaction: whether using both together behaves differently from the sum of the separate effects.

For each effect, show quality measures and resource/user-dependency measures separately. Also show every run, including incomplete runs and unusual failures. Do not hide resource-heavy runs or average away failed pairs.

### Replication

**Phase 0 — harness dry run:** deterministic fake-model tests for file isolation, tool restrictions, log integrity, turn/call limits, output validation, and simulated request-input behaviour. No live model.

**Phase 1 — one run per cell:** four-run feasibility pilot. Its purpose is to test whether all four conditions can complete the task and whether the logs and rubric are usable. No efficacy claim, even if the scores look different.

**Phase 2 — replicated blocks:** choose the number of independent four-cell blocks after reviewing Phase 1 costs and score variance. Pre-register the replication count, randomisation seed/method, exclusions, and analysis before collecting the next block. Do not select a sample size after looking at which condition won. A single block cannot establish general skill effectiveness.

For a larger claim, calculate a defensible sample size from pilot variability and a predeclared smallest meaningful difference. Preserve model and skill versions; if a model or skill changes, treat it as a new experiment version rather than pooling runs silently.

## 11. Validity and exclusion rules

A run is **instrumentation-valid** only if the run log validates, the task and condition hashes match the manifest, all writes remain in the output directory, and the three deliverables can be read.

A run is **task-complete** only if the three required deliverables exist, parse where applicable, and are not empty.

Keep separate statuses for:
- instrumentation valid/invalid;
- task complete/incomplete;
- resource capped/not capped;
- user-dependency attempt count;
- scoring complete/not scorable.

Do not exclude an incomplete or poor run simply because it makes a condition look bad. Exclude only a predeclared instrumentation or infrastructure failure that makes the evidence unusable; retain it in the archive with its reason.

## 12. Privacy and execution gate

The old real-model workflow stores raw requests/responses as GitHub Actions artifacts in a public repository. That is not suitable for a blinded experiment and can expose the condition and full skill text.

**Do not dispatch the real-model experiment from the current public workflow.** Before Phase 1:
- choose a private evidence destination and verify its actual access permissions;
- keep condition mapping and raw request/response artifacts private and separate from assessor packets;
- verify that blind labels cannot be mapped to conditions by someone with read access to the scoring packets;
- use a planning-only runner with no generated-code execution, shell access, network access, or live user-interaction tool; the only input-request mechanism is the simulated recorder;
- ensure the evaluator reference set is not mounted in the agent workspace.

The planning-only design removes the need to execute model-written software, but logs may still include prompts and full skill text. They remain controlled evidence.

## 13. Interpretation boundary

This experiment can show whether the tested MP and CT versions change the agent's observable checklist coverage, evidence handling, autonomy, output quality, or resource use on this fixed planning task.

It cannot prove:
- general intelligence or general reasoning improvement;
- that a skill works across all tasks or models;
- that more discovered items are always better;
- that a deferred project-owner decision is a failure;
- that one task-specific outcome establishes the effect in a different domain.

Retain the distinction between **wider arena**, **valid consideration**, **resolved work**, **unresolved decision**, and **user homework**. These are not interchangeable.
