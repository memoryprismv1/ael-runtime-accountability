# AEL implementation log

This is the chronological engineering record for changes to the AEL Runtime repository. It records implementation, rationale, verification, and remaining work. It is not a replacement for the author's AEL framework, source essays, or specifications.

## 7 November 2026 — Multi-user accountability and context intervention

### PR [#30](https://github.com/memoryprismv1/ael-runtime-accountability/pull/30): schema-v3 participant ledger

**Merged commit:** `1eb82061768f2b9a84a1e6f066bc3d64c3792406`

**Why:** An action log alone cannot show who was part of the decision chain but did not act. Actor attribution needed stable identities; passive participants and re-entry needed to remain historically reconstructable.

**Changed:** Added account-scoped participant identities; actor, represented-principal and recorder references; repeated participation periods with half-open event-sequence boundaries; schema-v3 export; additive migration that does not invent legacy identities; APIs for register/join/leave/reconstruct.

**Verification:** PR CI passed 79 tests across Python 3.11, 3.12 and 3.13.

**Boundary:** Membership records presence in the chain; it does not prove that a person read a message, was notified, understood it, or had authority to approve.

### PR [#31](https://github.com/memoryprismv1/ael-runtime-accountability/pull/31): CSV multi-user workflow fixture

**Merged commit:** `292fc42bcd7e0f4c930391fe69da17e910072c67`

**Why:** The host platform's participant list and multi-user transport were not available as a source to test against. A deterministic fixture was needed to exercise the ledger without inventing a new chat UI.

**Changed:** Added an idempotent roster importer, CSV workflow runner, six example identities and a 16-step simulated workflow. It demonstrates a manager joining late, being present through proposal/approval without acting, separate assistant proposer and human approver, and a requester leaving and rejoining.

**Verification:** PR CI [#442](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42375531422) passed 82 tests across Python 3.11, 3.12 and 3.13.

**Boundary:** This is a deterministic AEL integration fixture, not a live ChatGPT or hosted multi-user adapter.

### PR [#32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32): active membership and external context interventions

**Merged commit:** `301fb4bec68829460509851d83d2e225a859faad`

**Why:** The participant registry initially recorded membership but did not stop an explicitly identified person from acting before joining or after leaving. Separately, changes to shared instructions/context can alter what a model receives without changing the visible message transcript.

**Changed:**

- Added active-membership checks at the canonical event append boundary for explicitly identified human/AI actors, using the existing half-open participation intervals.
- Preserved explicit exceptions for reserved compatibility actors and system/service identities.
- Added a pre-write actor membership check to branch proposals, so a rejected action does not leave a branch row behind.
- Added `record_context_intervention`, which appends a versioned `context.intervened` event with resource ID/type, actor, authority, source reference, previous/current content hashes, and exact context text.
- Hydration injects only the latest version per resource; earlier versions remain in canonical history.
- Context intervention content is protected during packing; its metadata is included in the audit sidecar, not as separate sidecar material in provider input.
- Updated the README, multi-user format, context intervention guide, test report, roadmap and handoff.

**Verification:** PR CI [#445](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42377856668) passed 85 tests on each of Python 3.11, 3.12 and 3.13. The passing run was on the PR head immediately before merge; the merged commit contains the same tested code plus the final documentation.

**Boundary:** The experiment demonstrates that AEL can represent a context intervention which changes hydrated model input while leaving the user/assistant message transcript untouched. It does not reproduce live ChatGPT shared-project behaviour or prove that an external platform delivered the context to a real model request.

## Current limits carried forward

1. **Supporting action paths:** Active-membership enforcement is at the canonical event append boundary and before branch-proposal writes. Direct supporting-table operations—especially memory lifecycle rows and checkpoint creation—still need review so they cannot bypass the same boundary.
2. **Approval permission:** Membership is not permission. A separate capability/delegation policy is not implemented. In particular, a role string such as `approver` must not itself be treated as proof of authority.
3. **Context scope:** Intervention tracking is currently scoped to one account/project/chat. Cross-chat propagation of project instructions or context files is not implemented.
4. **Host integration:** A future adapter needs authenticated participant identities, reliable join/leave events, trusted resource identity/source, and correlation between the AEL event and the actual model-input hash.
5. **Live model/platform evidence:** Current tests establish deterministic ledger and model-input construction properties. They do not establish real-model quality or hosted ChatGPT behaviour.

## Repository boundaries preserved

- AEL runtime events and context-intervention records belong in this repository.
- Q-Batch owns experiment execution, shared experiment logging and cross-run evidence.
- The Differential was not modified by PRs #30–#32. It remains reference material unless a separate write is justified and explicitly approved.
