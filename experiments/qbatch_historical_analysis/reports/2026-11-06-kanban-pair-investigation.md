# Q-Batch Kanban pair — tool-loop investigation

**Attempt:** 3 November 2026, pair `ctab-20261103T102902-4c9dbe`  
**Task context:** `ct-skill-on-off-kanban-v1`  
**Model:** `qwen2.5-coder:7b` (same model digest in both arms)  
**Purpose:** explain the observed failure to complete; not an independent acceptance assessment.

## Condition assignment

| Arm | Skill condition | Elapsed time | Model requests / responses | Tool calls | Run result |
|---|---|---:|---:|---:|---|
| A | Skill ON | 14m 52s | 24 / 24 | 24 | Failed to call `finish` within 24 turns |
| B | Skill OFF | 12m 08s | 24 / 24 | 24 | Failed to call `finish` within 24 turns |

Condition was identified from the pinned skill hash in `manifest.json`, not from the A/B arm label.

## What the tool log shows

Each arm repeated the same three-tool sequence eight times:

1. `submit_plan`
2. `list_files`
3. `read_file` for `STARTER.md`

The first `submit_plan` succeeded. The following seven submissions in each arm were rejected with `ValueError: plan may be submitted only once`. The model nevertheless attempted to submit the same plan again in later cycles.

`list_files` repeatedly returned the same single file, `STARTER.md`. `read_file` repeatedly returned that same 238-byte starter note. The application-source ZIP saved at the end of each run contains only `STARTER.md`.

## Work that is absent from the logs

Neither arm recorded any:

- `command_started` or `command_finished` event;
- `file_changed` event;
- code-writing or patch-producing tool call;
- independent acceptance-suite execution.

The final `test_result` says the acceptance suite was **not run** because the agent did not finish. The run therefore has no acceptance score.

## Interpretation

This is a repeated planning/inspection loop, not a completed Kanban implementation that failed its tests. The visible failure is the agent's inability to move on after the duplicate-plan tool error. The logs establish the repeated tool sequence and the tool's rejection response; they do not, by themselves, establish why the model failed to recover from that response.

The skill-on and skill-off arms had the same observable workflow outcome and tool-call sequence in this pair. Their elapsed times differ, but one paired attempt with no completed task and no acceptance score cannot establish a meaningful speed or quality difference.

## Correction already made in the source repository

This is no longer an outstanding code fix. The AEL source repo now detects this exact duplicate-plan rejection, emits an `agent_loop_detected` event with reason `duplicate_plan_submission`, and stops immediately instead of spending the remaining inference budget in the loop.

- Fix merged to main in commit [`b87cb320cc53e59357fd334fbdd8b46fab899a2f`](https://github.com/memoryprismv1/ael-runtime-accountability/commit/b87cb320cc53e59357fd334fbdd8b46fab899a2f).
- A deterministic regression test verifies the runner stops after the duplicate submission, records only one accepted plan, and retains the rejected tool call in the audit trail.
- Post-merge CI [run #41794072403](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41794072403) completed successfully on 4 November 2026.

That CI run tests the runner's behaviour with a controlled fixture. **It is not a new real-model run.** No real-model retry has been launched after the correction.

## Next step

The next experimental step is a new manual-dispatch pair using the same frozen task bundle, with no simultaneous change to the Critical Thinking skill. Before dispatch, settle two safeguards:

1. The real-model workflow and its raw request/response artifacts are in a **public repository**, so this is not a confidential or truly blinded experiment. The model request artifacts can include the enabled skill text.
2. Generated application code is executed on an ephemeral hosted VM, but the repository runbook explicitly says this is **not a hardened security sandbox**.

If those boundaries are acceptable, run one pair, then check that both agents make file changes, execute controlled checks, call `finish`, and receive independent acceptance scores. Otherwise, move the pilot to a private evidence destination and a more isolated execution environment first.
