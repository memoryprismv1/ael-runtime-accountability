# AEL CT Experiment — Full Branch Handoff and Architecture

**Document purpose:** A whole-branch guide for understanding the current experiment, not just the path-root mechanism.  
**Branch:** `experiment/path-rooted-skill-matrix`  
**Baseline:** `main` at `0df6000a96a4ee5f2b370b70cd1b27f4e9e55b40` when the experiment was branched.  
**Status:** Experimental implementation plus a newly added, not-yet-run CT model-output evaluation pilot. This is not a release and nothing here has been merged into `main`.

## 1. Executive summary

This branch is pursuing two separate questions:

1. **Can the CT task-precommitment workflow be integrated into AEL Runtime while keeping the existing implementation available as a clean control?**
2. **Does providing the pinned Critical Thinking skill improve observable investigation quality on the same tasks?**

Question 1 is a software/architecture question. The branch has an isolated CT copy, an inherited path variable, dependency pinning and integrity checks, a task state machine, a comparison harness, and CI coverage for the original runtime suites. An earlier snapshot of this architecture passed the configured regression matrix.

Question 2 is an empirical model-quality question. A fixed ten-case benchmark and scorecard/report tool have now been added. The benchmark has not yet been run against baseline and CT model conditions, and no result about reasoning improvement has been established.

Keep those results separate. A software test can establish a tested state transition or integrity check. It cannot establish that the model investigated better, that a generated case is true, or that the skill generalizes to other models.

## 2. What the branch is—and is not

The top-level baseline implementation remains the control tree. The experimental implementation lives under `ct/`. The design intentionally duplicates runtime code and supporting files instead of trying to import a shared runtime and toggle a boolean through it.

That duplication is deliberate experimental isolation. CT needs its own runtime entry point, dependency, task workflow and tests. A shared runtime with conditionals would make it harder to know which code and prompts a test actually exercised.

The path selector is not a boolean like `CT_AVAILABLE=true`. It is the active environment root, carried as `AEL_PATH`, and used to select the matching files and imports. This is more explicit than a feature flag, but it does not mean the CT skill is automatically injected into every model call. The skill is specifically inserted into the task precommitment generator's case-note and plan prompts.

### Scope boundary

| Included in this branch | Not implemented or not yet established |
|---|---|
| A baseline tree and isolated CT tree | A merge into `main` or a released AEL version |
| Path-rooted environment launch and manifest validation | A boolean CT selector or a runtime-wide automatic skill injection |
| Exact CT skill commit/blob pin and integrity validation | Automatic updates from the upstream moving branch |
| Case → approval → plan → approval → execution → verification records | An arbitrary external-app/browser executor |
| A local Ollama path for generating task case notes and plans | Direct ChatGPT/Claude website integration or a paid cloud API |
| Regression comparison of the two software environments | Proof that CT improves reasoning |
| A benchmark, scorecard, and descriptive report tool | A completed baseline/CT model-quality run |
| Evidence references and recorded verification outcomes | Independent proof that a model's claims or supplied evidence are true |

## 3. Branch identity, ancestry, and provenance

- Baseline revision recorded in both manifests: `0df6000a96a4ee5f2b370b70cd1b27f4e9e55b40`.
- The CT environment manifest records the precommitment implementation source branch revision as `eef81c3c083e163eaa8d9bbcfa4928f09ff05bec`.
- The vendored CT skill is from [cognitive-interface-ai-skills / critical-thinking/SKILL.md](https://github.com/memoryprismv1/cognitive-interface-ai-skills/blob/d1f23e2ad9dafd323940fc6b7a00f1700275d885/critical-thinking/SKILL.md).
- Pinned skill commit: `d1f23e2ad9dafd323940fc6b7a00f1700275d885`.
- Pinned Git blob SHA: `d7134969b124e39c04e343bed2ce2475f64b9a64`.
- Skill license stated in the dependency metadata: CC BY-NC 4.0, with attribution and license obligations.
- The broader AEL implementation retains its own ownership/licensing boundary. See the repository's ownership/license notes; pinning or bundling a skill does not change who owns the AEL source framework.

The exact skill pin is meant to make runs reproducible. It does not validate the skill. Updating the skill should be a reviewed, explicit dependency change that updates the version and integrity information rather than a silent fetch from upstream `main`.

## 4. Repository map: where to look

### Root / baseline and experiment harness

| Path | Responsibility |
|---|---|
| `runtime.py` | Original baseline runtime. It is intended to remain unchanged on this branch. |
| `ael_chat.py` | Original local interactive chat shell in the baseline tree. Intended to remain unchanged. |
| `experiment.json` | Root environment manifest; identifies `baseline-v2.8.1` and declares no additional skill dependency. |
| `ael_environment.py` | Environment path resolution, manifest parsing, dependency pin and integrity checks. |
| `run_ael.py` | Recommended environment-selecting launcher. Validates an environment, passes `AEL_PATH`, sets the subprocess working directory and import path, then runs that tree's runtime or chat entry point. |
| `compare_environments.py` | Runs each tree's standard-library unit test suite separately and compares per-test results. Writes a JSON report. |
| `EXPERIMENT_ENVIRONMENTS.md` | Path/dependency/comparison instructions; this document is the broader system handoff. |
| `.github/workflows/tests.yml` | Python matrix CI; compiles the runtime and, after the evaluation addition, the evaluator too; runs the synthetic evaluator tests and the baseline-vs-CT software comparison. |
| `tests/test_environment.py` | Path/manifest/dependency checks. |
| `tests/test_comparison_harness.py` | Tests the result parser/comparison logic. |
| `START_AEL_CHAT_CT.bat` | Windows convenience launcher for the CT chat environment. |

### CT environment

| Path | Responsibility |
|---|---|
| `ct/runtime.py` | Copy of the baseline runtime with environment-root checks and the task-precommitment CLI integration. |
| `ct/ael_chat.py` | CT-tree copy of the local interactive Ollama chat shell, with a path/tree consistency check. It is not itself a special CT reasoning UI. |
| `ct/run_ael.py` | Environment-local copy of the launcher. Normal entry from the repository root should use root `run_ael.py --path ct ...`. |
| `ct/ael_environment.py` | Environment-local copy of the resolver/manifest/integrity functions. |
| `ct/experiment.json` | CT experiment identity and required pinned skill dependency. |
| `ct/dependencies/critical-thinking/SKILL.md` | Vendored skill snapshot. |
| `ct/dependencies/critical-thinking/DEPENDENCY.json` | Source, commit, blob hash, license, attribution and update policy. |
| `ct/ael_task_precommitment.py` | The new task-level precommitment lifecycle, artifact store, decision gates, action records, verification and export functions. |
| `ct/tests/test_task_precommitment.py` | State-machine, hash-binding, approval-order, append-only and export tests. |
| `ct/tests/test_environment.py` | CT-local environment checks. |
| `ct/tests/test_runtime.py`, `ct/tests/test_local_bridge.py` | Copied baseline runtime and mock local-model-bridge tests, kept in the isolated tree. |
| `ct/CRITICAL_THINKING_PRECOMMITMENT_LOG.md` | Development/precommitment record from the earlier task-precommitment implementation. |
| `ct/TEST_REPORT.md`, `ct/NEXT_STEPS.md`, `ct/LOCAL_MODEL_BRIDGE.md` | Limitations, future work and local Ollama integration notes. |

### Added model-output evaluation pilot

| Path | Responsibility |
|---|---|
| `CT_EVALUATION_PLAN.md` | Protocol for testing CT's effect on visible investigation outputs. |
| `ct-evaluation/benchmark-v1.json` | Fixed set of ten self-contained cases and case-specific scoring anchors. |
| `ct-evaluation.py` | Initializes a JSON scorecard, validates scorecards, and computes descriptive summaries and paired deltas. It does not call a model or auto-score answers. |
| `ct-evaluation/test_harness.py` | Eleven deterministic sanity tests using synthetic fixtures, not real model outputs. |

The `ct/` tree includes a number of copied AEL documents (context budget, memory workflow, usage disposition, delta-first delivery, source inventory, licensing and other baseline materials). Their presence preserves an independent, readable copy of the experimental environment; it does not mean every such subsystem was newly rewritten for CT. The primary new task-level subsystem is `ct/ael_task_precommitment.py`, supported by the environment guard/pinning and experiment harness.

## 5. Path-rooted environment selection

The path-rooted approach is the mechanism for separating the two implementations.

### Startup sequence

1. `run_ael.py` accepts `--path` or `--path=...`; without it, it uses the inherited `AEL_PATH` or the root baseline by default.
2. `ael_environment.py` resolves the path and requires that it remain inside the repository. The selected directory must contain `runtime.py`, `ael_chat.py` and `experiment.json`.
3. It parses the manifest, checks the schema and environment identifier, and validates declared dependencies.
4. For each dependency, the validator checks its relative path stays inside the environment, required dependencies exist, and the declared Git blob SHA-1 and/or SHA-256 matches the file bytes. A `git:<commit>` version must agree with `source_commit`. Missing or mismatched required dependencies fail closed.
5. The launcher chooses the selected tree's `runtime.py` or `ael_chat.py`, sets the child process's `AEL_PATH` and `PYTHONPATH` to that root, and makes it the working directory.
6. The CT runtime/chat entry points check that their file directory agrees with `AEL_PATH`; the CT runtime also invokes the environment/manifest validation at startup.

A normal Python global variable does not cross process boundaries automatically. Here `AEL_PATH` is an environment variable explicitly passed to child processes and paired with the working directory/import path. This makes the chosen environment inspectable and reduces accidental cross-tree imports.

### Manifests

Root `experiment.json` identifies the baseline as `baseline-v2.8.1` with an empty dependency map. CT `ct/experiment.json` identifies `ct-task-precommitment-v1`, records the baseline revision and integration source revision, and declares the skill as a required dependency.

The manifest is a local integrity/dependency registry; it is not a package installer and does not fetch or install external packages. `AEL_PATH` selects a directory; the manifest verifies that the selected directory describes the expected experiment and has its pinned local dependency.

### Use the wrapper

From the repository root:

~~~bash
# Baseline runtime help
python run_ael.py runtime --help

# CT runtime and task help
python run_ael.py --path ct runtime task --help

# CT's local interactive chat shell
python run_ael.py --path ct chat

# Deterministic software comparison
python compare_environments.py --out comparison-report.json
~~~

Directly invoking `python ct/runtime.py` bypasses the root launcher step; prefer the documented wrapper so selection and startup validation happen in one predictable path. The CT runtime also has its own consistency checks, but the wrapper makes the selected environment explicit.

## 6. What the pinned Critical Thinking skill says to do

The bundled skill is labelled **provisional**, explicitly not validated as a reliable capability, and scoped to curiosity-led exploration, mismatch investigation and evidence-based revision. It preserves the user's three inquiry triggers:

- “I want to know more about this.”
- “The answer makes no sense to me for XYZ reasons.”
- “Dig until the XYZs are reconciled.”

Its operating posture is to stay in the inquiry with the user and bring initiative without automatically agreeing or prematurely formalizing every question. Behaviours include following the actual curiosity; finding the specific mismatch; building and comparing explanations; making discriminating predictions before seeing evidence where useful; investigating existing research; separating observation, mechanism, function, evolutionary explanation, engineering analogy and deployment; trying to break the preferred explanation; correcting in good faith; and leaving a result honestly marked as supported, contradicted, ambiguous, not tested or unresolved.

These are flexible inquiry moves, not a mandatory form to mechanically fill out on every task. “Reconciled” does not mean forced into a tidy answer. The skill says Memory Prism is distinct and optional; its checklist remains fixed, tiny and read-only, and it is not made the governing framework for ordinary CT work.

## 7. How CT is actually integrated with AEL

### Crucial distinction: availability versus use

The skill is present and pinned in the CT environment, but the code does not establish a global instruction that automatically wraps every chat turn in the CT skill. The explicit prompt integration is in `ct/ael_task_precommitment.py`:

- `generate-case` builds a case-investigation prompt and includes the full pinned skill text as model-facing context.
- `generate-plan` requires an approved current case first, then builds a plan prompt from the skill plus the approved case notes.

These commands use the existing local Ollama adapter (`runtime.ollama_chat`). They require a running local Ollama service and a locally available model. The normal `chat` command remains the copied interactive chat shell and should not be assumed to load CT automatically for every turn.

### Why a task-level lifecycle was added

The baseline already has a document-revision lifecycle, context projection, memory-use controls and a local text-chat bridge. Those mechanisms do not represent an entire requested task with a case, a plan derived from that case, approval of both exact versions, execution records, and final task verification. The CT branch adds a separate task lifecycle instead of stretching document revision states to stand for autonomous work.

### Task workflow in plain language

1. **Create task.** Store the user request, task scope and dependency identity.
2. **Generate or submit case notes.** Case notes should state the interpretation and boundaries, observed facts versus assumptions, sources and support, alternatives, counterchecks, unresolved issues, risks and recommendation. Generation uses the pinned skill; manual submission is also possible.
3. **Approve or reject the current case.** The user/delegated decision is recorded against the exact case artifact and hash. Approval authorizes planning from this case; it is not a guarantee that the case is true.
4. **Generate or submit an implementation plan.** The plan must be derived from the current approved case. It specifies ordered actions, preconditions, expected outputs, constraints/permissions, risks, failure handling, completion criteria and how each significant action/claim will be checked. It must not execute the plan.
5. **Approve or reject the exact plan.** The decision is recorded against the exact plan artifact/hash.
6. **Begin execution.** The runtime refuses to begin unless a current case and plan exist, the current case is approved, the current plan is approved, and the plan is bound to the current case hash.
7. **Record actions and outcomes.** Each action can be marked started, completed, failed or skipped, with description, notes and an optional evidence reference. Completion records the outcome summary and output references.
8. **Verify.** The task can record pass, partial, fail or unverified status and per-check results. Passing checks must refer to evidence; “not tested” should remain visible rather than being rewritten as success.
9. **Export/show the audit.** The snapshot can be exported as Markdown or displayed as a compact task state.

### State and approval protections

- Case notes, implementation plans and verification reports are immutable task artifacts at the database/API level: database triggers reject update/delete.
- Task decisions, task events, action records and verification records have append-only triggers too.
- Each artifact stores a SHA-256 of its content and the CT skill commit/blob identity.
- A plan stores `based_on_case_sha256`, binding it to the exact case content from which it was produced.
- Submitting a replacement case clears the current plan; the old plan and decisions remain in history.
- A plan cannot be submitted until the current case has been approved.
- Execution cannot start without approval of both the current case and the plan that refers to it.
- The code rejects replacing case/plan artifacts after execution starts. A new task is required for a changed post-start scope.
- Task events are also appended to the existing AEL runtime event ledger so the task lifecycle is visible within the wider account/project/chat history.

The database records can make the process reconstructable and detect ordinary in-database artifact-content mismatches. They are not proof that the evidence is true, nor are they a security boundary against an operator or agent that bypasses or edits the runtime/database outside the intended interface.

## 8. Task CLI reference

All commands below run through the CT environment:

~~~bash
python run_ael.py --path ct runtime task --help
~~~

The task subcommands currently exposed are:

| Subcommand | What it does |
|---|---|
| `create` | Create task ID, request, project/chat scope and model label. |
| `generate-case` | Use the pinned skill and local Ollama to draft case notes for review; writes the generated text to a file and registers an artifact. |
| `submit-case` | Register supplied case-note text from a file. |
| `decide-case` | Approve or reject the current case notes, with an optional decision note. |
| `generate-plan` | Use local Ollama and the pinned skill to draft a plan from the approved case. |
| `submit-plan` | Register supplied plan text; current case must already be approved. |
| `decide-plan` | Approve or reject the current plan. |
| `begin` | Request authorization to start execution; all approval/hash conditions must pass. |
| `block` | Record that approved execution is blocked or stopped. |
| `log-action` | Record an action description, status, evidence reference and note. |
| `complete` | Record completion summary and output references. |
| `verify` | Add a verification status and checks from a JSON file. |
| `export` | Export the task snapshot as an auditable Markdown document. |
| `show` | Show current task/dependency identifiers and artifact/decision/action/event counts. |

CLI shape is implemented; the workflow is not a general-purpose action runner. An external action has to be performed by a human or another permitted tool/process, then represented in the ledger. The current code does not itself browse websites, edit arbitrary third-party applications, or prevent an external agent from acting outside AEL.

### Illustrative sequence

The actual model, task IDs, evidence paths and verification checks must be supplied for the real run.

~~~bash
python run_ael.py --path ct runtime task create --project demo --chat pilot --id task-001 --request "Investigate X and propose a bounded implementation."

python run_ael.py --path ct runtime task generate-case --project demo --chat pilot --id task-001 --model LOCAL_MODEL_NAME --out case-notes.md
python run_ael.py --path ct runtime task decide-case --project demo --chat pilot --id task-001 --decision approve --note "Reviewed case notes."

python run_ael.py --path ct runtime task generate-plan --project demo --chat pilot --id task-001 --model LOCAL_MODEL_NAME --out implementation-plan.md
python run_ael.py --path ct runtime task decide-plan --project demo --chat pilot --id task-001 --decision approve --note "Reviewed plan."

python run_ael.py --path ct runtime task begin --project demo --chat pilot --id task-001
# After separately performing each allowed action, record what actually happened:
python run_ael.py --path ct runtime task log-action --project demo --chat pilot --id task-001 --description "Run test suite" --status completed --evidence-ref "test-report.txt"
python run_ael.py --path ct runtime task complete --project demo --chat pilot --id task-001 --summary "Implementation complete; see limitations." --output-ref "result.md"

# checks.json must hold explicit checks and evidence_refs for passing checks.
python run_ael.py --path ct runtime task verify --project demo --chat pilot --id task-001 --overall-status partial --checks-file checks.json
python run_ael.py --path ct runtime task export --project demo --chat pilot --id task-001 --out task-audit.md
~~~

The CLI's required arguments can be inspected with each subcommand's `--help`. The example is a workflow illustration, not evidence that a live model or external executor has run.

## 9. Existing AEL runtime mechanisms retained in the CT copy

The CT tree inherits the baseline V2.8.1 runtime mechanisms rather than replacing them. The relevant concepts include:

- Append-only history and a separate active-context projection.
- Explicit provenance, authority, inference kind and truth-status fields.
- Branch decisions and exclusion of rejected branch output from active context.
- Memory review/promotion stages, and the separation of retaining information from permitting it to influence a future answer.
- Context budgeting: protected user-originated material stays verbatim; protected overflow fails closed; optional events are included/omitted whole rather than silently truncated.
- Delta-first artifact revision: propose a structural delta, obtain a decision, expand only the accepted immutable proposal, and verify declared changed-section scope against the pinned base before marking release-ready.
- A strict model-input allowlist: send only bounded working context and current message, not full audit logs, rejected drafts, or diagnostic sidecars.
- Optional loopback-only local Ollama bridge and interactive chat shell.

These inherited features explain the scale of the CT copy. They are not each new CT innovations. The main CT additions are the pinned skill path, environment consistency/integrity checks, task precommitment, its tests and the comparison machinery.

## 10. Two distinct test tracks

### A. Software / architecture track

`compare_environments.py` resolves and validates each environment, runs the same `python -m unittest discover -s tests -v` command with separate working directory, `PYTHONPATH` and `AEL_PATH`, parses individual test outcomes, and writes suite summaries and pairwise comparisons. It records experiment IDs and dependency information, counts test outcomes, reports shared test differences and identifies tests present in only one tree. It flags a baseline pass becoming a failure in the compared environment.

Use:

~~~bash
python compare_environments.py --out comparison-report.json

# Additional environment roots can be compared in the same invocation:
python compare_environments.py --environment baseline=. --environment ct=ct --environment ct_xyz=ct_xyz --out comparison-report.json
~~~

CI is configured for Python 3.11, 3.12 and 3.13. The workflow compiles the trees and scripts, runs the separate software test suites, and uploads machine-readable comparison JSON artifacts.

**Known historical result:** the earlier path-rooted implementation snapshot at commit `9c44dec901a3fdbb5dfcadcdac9a1d8e68471125` had a reported passing CI matrix at [workflow run 39439362515](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39439362515): baseline 66 tests passed; CT 75 tests passed; 64 shared tests had identical outcomes, with no reported regressions. That run predates the newly added CT evaluator and its CI step. Do not treat it as validation of the latest evaluator changes.

### B. Model-output / CT efficacy track

The new pilot is intentionally separate. It uses `ct-evaluation/benchmark-v1.json`, benchmark ID `ct-closed-world-pilot-v1`, version `1.0.0`, with ten fixed tasks:

1. Reconcile a stock ledger's arithmetic mismatch.
2. Detect ambiguity from overlapping categories.
3. Handle a dashboard generated from stale underlying state.
4. Compare roof leak and pipe leak hypotheses.
5. Challenge a preferred deliberate-blame hypothesis without over-attribution.
6. Update a failure-rate claim after corrected classifications.
7. Reconcile a timeline with a known camera clock offset but unknown other offsets.
8. Separate a fertilizer association from an indoor/outdoor confound.
9. Check proportionality on a simple unit conversion.
10. Separate visual observation from a proposed explanation and stronger causal claim.

Conditions:
- **Baseline:** task without the CT skill.
- **CT:** same task with the exact pinned skill genuinely loaded.
- **Optional neutral control:** format/presentation instructions of comparable length without substantive CT guidance.

Keep model/provider/version/settings, task wording, available evidence/tools and isolated session state consistent. Capture raw responses verbatim. Score the visible answer against the same fixed case anchors; do not score hidden chain-of-thought or a model's self-assessment. Use blinded assessment when feasible, and retain notes for non-obvious ratings.

Score dimensions (case-specific applicability is defined in the benchmark): central accuracy; evidence fidelity; contradictions and alternatives; calibration of certainty/unknowns; and scope discipline/proportionality. The report gives descriptive means, sample counts, paired CT-minus-baseline/neutral case deltas, and case-level win/tie/loss counts. Inspect individual cases and regressions; ten cases are a pilot, not a statistically decisive benchmark.

The harness commands are:

~~~bash
# Blank scorecard
python ct-evaluation.py init --output ct-evaluation/run.json --model MODEL_NAME --model-version VERSION

# Optional neutral condition
python ct-evaluation.py init --output ct-evaluation/run.json --model MODEL_NAME --model-version VERSION --include-neutral

# Validate scorecard structure and required scores
python ct-evaluation.py validate ct-evaluation/run.json --require-complete

# Emit a machine-readable descriptive report
python ct-evaluation.py report ct-evaluation/run.json --out ct-evaluation/report.json

# Test the scorecard/report logic using synthetic fixtures only
python ct-evaluation/test_harness.py
~~~

The operator must record the exact model/version/provider, model settings, tool access, condition order, isolation method, CT skill commit/blob, raw outputs, score rationales and protocol deviations. A scorecard cannot prove that the CT skill was actually present in the model's context; that must be ensured and documented in execution. The evaluator script is a scorecard/report utility, not a model runner, and does not independently judge response quality.

**No CT efficacy result exists yet.** A passing evaluator unit test would only show that the report machinery calculates/validates the expected synthetic examples. Real controlled inference and scoring remain to be done.

## 11. Current verification state and remaining work

### Implemented in the repository
- Baseline and CT paths, manifests and launch wrapper.
- CT skill snapshot pinned to exact upstream commit/blob with attribution and license information.
- Startup dependency/path checks that fail closed on mismatch.
- Separate task-precommitment schema and CLI; artifact/decision/action/verification records; hash-linked case and plan; append-only triggers and Markdown audit export.
- Regression comparison script and CI matrix.
- Fixed pilot benchmark, manual scorecard/report tool and seven synthetic evaluator tests; CI was updated to run these tests.

### Verified previously (not all on the latest branch tip)
- The earlier architecture comparison had a reported green Python 3.11/3.12/3.13 workflow with baseline 66/66 and CT 75/75, 64 shared outcomes identical and no regressions.
- The task-precommitment test file contains targeted tests for dependency hash verification, approvals, case change invalidation, plan/case hash binding, retained append-only audit records, evidence-backed verification and CLI exposure.
- The evaluator contains tests using synthetic fixture responses for benchmark structure, scorecard validation, paired score arithmetic, missing-score behavior and invalid scores.

### Not established yet
- The newest CI run after adding `ct-evaluation.py` and updating the workflow. The earlier green run predates this change.
- A live run of `ct-evaluation/test_harness.py` against the current branch inside GitHub Actions or a local checkout.
- Any real model inference on the ten benchmark cases.
- Whether the intended CT skill is actually included consistently in each CT evaluation response.
- Whether CT improves quality, whether neutral instructions explain any apparent change, and whether results transfer to other tasks or models.
- General action execution outside the local CLI/Ollama integration, external-app orchestration, semantic verification, and security against actors bypassing the runtime.

### Practical next session order

1. Check the latest branch CI after the evaluator additions. First resolve any syntax/import/test failures.
2. Run the normal baseline-vs-CT comparison and inspect JSON artifacts—not just the green/red badge.
3. Confirm the pinned skill commit/blob and choose the actual locally available model/runtime for the model-output pilot.
4. Freeze the run configuration and benchmark hash; generate one scorecard and capture responses for the conditions with isolated sessions.
5. Score against the fixed rubric. Inspect case-level outcomes, failure modes and simple-task regression before interpreting the aggregate.
6. Only then decide whether to test larger benchmark coverage, open-world research cases, a neutral control, or additional skill combinations.

## 12. Interpretation and safety boundaries

- The CT skill is provisional. Its intended behaviours are a hypothesis to evaluate, not a guaranteed property of the model.
- Skill pinning makes the input reproducible; it does not make the skill authoritative or correct.
- Approval authorizes the next stage on the submitted case/plan. It does not certify their truth.
- Runtime-managed append-only records are an accountability aid, not tamper-proof proof or an external enforcement boundary.
- A recorded check can be inspected and reproduced where evidence permits; a model-written assertion that a check passed is not independent proof.
- The existing textual document conformance checker checks changed-section scope, not semantic fulfilment of an approved request.
- The local Ollama bridge was tested historically with mock HTTP endpoints; the prior development environment did not have Ollama installed, so real inference was not established there.
- No action outside this runtime should be assumed blocked just because no approved task record exists.
- The original AEL source framework remains authoritative for AEL concepts. This handoff describes the current experimental implementation; it does not replace the source framework or declare an AEL release.

## 13. Reference links

- [Branch: experiment/path-rooted-skill-matrix](https://github.com/memoryprismv1/ael-runtime-accountability/tree/experiment/path-rooted-skill-matrix)
- [This full handoff](BRANCH_STATE_AND_ARCHITECTURE.md)
- [Path, manifest and test instructions](EXPERIMENT_ENVIRONMENTS.md)
- [CT skill dependency manifest](ct/experiment.json)
- [Vendored CT skill](ct/dependencies/critical-thinking/SKILL.md)
- [Task precommitment implementation](ct/ael_task_precommitment.py)
- [Task precommitment tests](ct/tests/test_task_precommitment.py)
- [Software comparison harness](compare_environments.py)
- [CT efficacy protocol](CT_EVALUATION_PLAN.md)
- [Fixed ten-case benchmark](ct-evaluation/benchmark-v1.json)
- [Scorecard/report tool](ct-evaluation.py)
- [Synthetic evaluator tests](ct-evaluation/test_harness.py)
- [Earlier green CI run, predating evaluator additions](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39439362515)
