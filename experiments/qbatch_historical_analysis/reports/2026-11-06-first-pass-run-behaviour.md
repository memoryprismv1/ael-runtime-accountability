# Q-Batch first-pass report — run behaviour, not efficacy

**Date:** 6 November 2026  
**Source:** four paired A/B audit archives in `memoryprismv1/ael-runtime-accountability`  
**Purpose:** describe what happened in each run and check whether the skill-on and skill-off arms behaved differently on the observable workflow measures.

## How conditions were identified

The A/B letter is not the treatment label. The condition was read from each run's manifest:

- **Skill ON:** `skill_file_sha256` matches the pinned Critical Thinking skill.
- **Skill OFF:** no skill file hash is recorded.

Pinned source: `memoryprismv1/cognitive-interface-ai-skills/critical-thinking/SKILL.md`, commit `d1f23e2ad9dafd323940fc6b7a00f1700275d885`, SHA-256 `db0b0e626bd3d044b9e8cca14143c642a2e39eee5e1c194e88f0a16f5f94f37b`.

All four attempts use the same model identity and task bundle hash. The final attempt also identifies the fixed Kanban pilot context `ct-skill-on-off-kanban-v1`. The earlier three are retained as preliminary pilot/harness attempts, not successful scored trials.

## Pair-by-pair summary

Elapsed time is calculated from the first `run_started` event to the final `run_finished` event in each run log. Model request/response counts are counted from `model_request` and `model_response` events; separate request-started/succeeded instrumentation events are not double-counted.

| Attempt | Skill OFF | Skill ON | What happened |
|---|---|---|---|
| 21 Oct, pair 1 | A: 24 requests, 24 responses, 0 tool calls, 8m 19s | B: 24 requests, 24 responses, 0 tool calls, 10m 57s | Both returned without tool calls for all 24 turns; neither called finish. |
| 21 Oct, pair 2 | B: 24 requests, 24 responses, 3 tool calls, 15m 49s | A: 24 requests, 24 responses, 3 tool calls, 4m 01s | Both made 3 tool calls, then repeatedly returned without tool calls and did not finish within 24 turns. |
| 22 Oct, pair 3 | A: request timed out at 180s; 0 completed requests/responses; 0 tool calls | B: same | Both failed on the first model request. |
| 3 Nov, Kanban pair | B: 24 requests, 24 responses, 24 tool calls, 12m 08s | A: 24 requests, 24 responses, 24 tool calls, 14m 52s | Both made 24 tool calls but did not call finish within 24 turns. Acceptance suite was not run. |

## What is consistent across the pairs

- Both conditions have the same broad outcome in every pair.
- Neither condition produced a completed run.
- No pair produced a usable independent acceptance score.
- The observable tool-call counts match within each pair: 0, 3, 0 and 24 respectively.
- The dominant failure pattern changes by attempt: no tool dispatch, repeated no-tool responses, first-request timeout, then reaching the tool-call limit without finishing.

This is useful evidence about the workflow and the runner. It is **not evidence that the Critical Thinking skill has no effect**: the runs never reached the independent acceptance measurement that was meant to assess the result.

## Reporting rules from here

1. Keep each A/B pair together. Count four paired attempts, not eight independent experiments.
2. Determine skill ON/OFF from the manifest's pinned skill hash, never from A/B.
3. Separate events that show an intention (for example, `plan_submitted`) from evidence of action (for example, `tool_call`, `command_started`, `file_changed`, and `command_finished`).
4. Separate model/runner failure from task failure. A run that never finishes cannot be treated as a completed task with a bad result.
5. Report acceptance scores only when the independent acceptance suite actually ran and produced a score.
6. Do not average the four attempts into a performance number or make efficacy claims. Show the four pairs and their observable differences.

## Next useful report

The next pass should inspect the captured tool inputs/outputs and resulting project files for the 3 November Kanban pair. That is the only pair with 24 dispatched tool calls per arm. We can then say what each agent actually changed, whether the two workspaces differ, and exactly why the runner did not record completion. It still will not be an acceptance score, but it may explain the failure to finish.

