# Checklist-elaboration runner — implementation status

**Status:** runner merged into AEL main; pre-merge and post-merge CI passed; private manual-only execution workflow pinned to the merge commit; **no real-model block has been dispatched**.

## Code implementation

- Source repository: [memoryprismv1/ael-runtime-accountability](https://github.com/memoryprismv1/ael-runtime-accountability)
- Pull request: [#29 — Add autonomous checklist-elaboration Q-Batch runner](https://github.com/memoryprismv1/ael-runtime-accountability/pull/29) (**merged** 6 November 2026)
- Squash-merge commit on AEL `main`: `26507b60b44030a9f6febc65658b287ba7cf3d73`
- Pre-merge CI: [run #407](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42222246577) — Python 3.11, 3.12 and 3.13 all passed.  
- Post-merge CI: [run #408](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42235268964) — successful on merge commit `26507b60b44030a9f6febc65658b287ba7cf3d73`.

The new module is `experiments/checklist_elaboration/`. It is separate from the historical Kanban runner. It verifies the frozen task fixture, checks the exact pinned MP and CT skill commits/files, creates an isolated workspace for each condition, and exposes only file listing, file reading, deliverable writing, simulated input requests and finish.

The simulated `request_input` tool records a hypothetical request, immediately returns no answer, contacts nobody and requires the agent to continue. The runner captures request/response usage, tool events, file reads/writes, repeated tool/input loops, resource use and deliverable validation. It randomises four internal factorial cells and blind labels separately.

The new deterministic tests use a fake model. CI does not call Ollama and does not create real-model evidence.

## Private execution workflow

The manual-only workflow is stored in this private repository: [Q-Batch checklist-elaboration feasibility block](https://github.com/memoryprismv1/the-differential-library/blob/main/.github/workflows/qbatch-checklist-elaboration.yml). It is available from the [Actions page](https://github.com/memoryprismv1/the-differential-library/actions/workflows/qbatch-checklist-elaboration.yml).

After PR #29 merged, the private workflow was updated to pin AEL's merge commit `26507b60b44030a9f6febc65658b287ba7cf3d73`. The workflow definition stays in Differential because it writes private model records and the hidden condition key there. The user confirmed they are the only reader of that private repository. The workflow has not been dispatched.

It checks out the exact runner and skill commits, downloads the fixed local model on a GitHub-hosted VM, and runs one randomized four-condition feasibility block. It has no push, pull-request, schedule or automatic trigger.

The workflow commits durable evidence to:

`projects/ael-runtime-accountability/evidence/checklist-elaboration-runs/<UTC-date>/<run-id>/`

The archive separates:
- raw run logs, including model prompts/responses and the skill text read by the agent;
- assessor score packets, without raw prompts, skill text or condition mapping;
- the blinded block summary;
- the controller condition key.

The raw evidence and key are in the private Differential repository. Repository permissions are not per-folder permissions, so any future reader added there would also be able to read the raw evidence and controller key. Keep blinded assessors outside the repository and provide only score packets through a separate channel.

Actions artifacts are also uploaded as short-term copies. The durable archive in Differential is the retention path. The workflow runs only on an explicit manual dispatch; no model run has been started.

## Remaining before an actual model run

1. PR #29 is merged. The runner source blob in AEL `main` was verified identical to the tested PR head.
2. The private Differential workflow is now pinned to the merged AEL commit `26507b60b44030a9f6febc65658b287ba7cf3d73`.
3. The user confirmed they are currently the only reader of the private Differential repository.
4. Manually dispatch **Q-Batch checklist-elaboration feasibility block** from the Actions tab of the private Differential repository.
5. Treat one run per condition as a feasibility pilot only. Do not claim MP or CT efficacy from the four runs.

**No model has been dispatched.** This work implemented the runner and storage path; it did not consume a model run or create experimental outcome data.
