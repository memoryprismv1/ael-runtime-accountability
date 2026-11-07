# AEL Runtime — Next Steps / Handoff

**Current build:** V2.8.1 prototype, extended on 7 November 2026 with schema-v3 participants, CSV multi-user workflow fixtures, active-membership enforcement at the canonical event boundary, and chat-scoped external context intervention records.  
**Current phase:** Validate participant action boundaries and context changes that alter hydrated model input without changing the visible message transcript.  
**Ownership:** AEL and the source architecture belong to the user. This is an implementation handoff, not a new AEL specification.

## Merged work already on main

- **PR [#30](https://github.com/memoryprismv1/ael-runtime-accountability/pull/30)** — participant registry, actor attribution, repeated membership periods and schema-v3 export. Squash commit: `1eb82061768f2b9a84a1e6f066bc3d64c3792406`. CI: 79 tests passed on Python 3.11/3.12/3.13.
- **PR [#31](https://github.com/memoryprismv1/ael-runtime-accountability/pull/31)** — CSV roster importer and 16-step multi-user workflow fixture. Squash commit: `292fc42bcd7e0f4c930391fe69da17e910072c67`. CI [#442](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42375531422): 82 tests passed on Python 3.11/3.12/3.13.
- Q-Batch remains the home for shared experiment logging and Q-Batch evidence. No Q-Batch or The Differential files were changed as part of these AEL changes.

## Current branch — participant enforcement and context intervention

Branch: `participant-enforcement-context-intervention` (not merged at the time of this handoff).

### Implemented in this branch

1. Canonical event appends require an explicitly identified human/AI actor to be an active member of the chat, or of the matching workflow where supplied. The half-open membership interval governs the check.
2. Reserved fallback actors and explicit system/service actors remain exempt for compatibility and runtime bookkeeping. A participant may self-join; the setup/system path may also provision membership.
3. Branch proposal validates active membership before writing the branch row, preventing a denied proposal from leaving partial branch state.
4. `record_context_intervention` appends versioned `context.intervened` events with resource ID/type, actor, authority, source reference, previous/current SHA-256, and exact content.
5. Hydration selects only the latest context version per resource. Prior versions remain in history; active context receives the newest content. The visible user/assistant message transcript is not rewritten.
6. The provider-facing input remains the existing allowlist. Intervention provenance/version details are in the audit sidecar, not sent as sidecar data to the model.

### Tests being added

- Identified actor denied before joining, accepted while active, denied after leaving.
- Denied pre-join branch proposal leaves no branch row.
- External context intervention changes the model-input hash and content while the user-message transcript remains unchanged.
- A later resource version supersedes the earlier version in active context while preserving both in history.
- Unjoined outsider and stale expected previous hash are rejected.

CI has not yet verified this branch. Do not treat the above as merged or green until the PR workflow completes.

## Known limits / next tests

1. **Supporting action paths:** audit and enforce membership for operations that write directly to supporting tables rather than through `append_event`, especially memory lifecycle rows, revision lifecycle rows, and checkpoint creation. Branch proposal has an explicit pre-write check already.
2. **Approval permission:** active membership is not approval authority. Define a separate capability/delegation rule and test an active participant with no approval permission attempting to approve. Do not infer permission from a display name or role label alone.
3. **Context scope:** current intervention support is account/project/chat scoped. It does not yet propagate a project instruction or uploaded context file into multiple chats. A host adapter must provide trusted resource identity, actor ID, source reference, and correlate the event with the actual model-input hash.
4. **Host identity source:** use the platform's authenticated participant list when available. Do not build a replacement multi-user UI unless a host integration demonstrably requires one.
5. **Real-model behavior:** mock/fixture tests establish ledger and model-input construction invariants, not the behavior of an actual hosted platform or local model.

## Repository boundaries

- AEL runtime activity and context-intervention receipts stay in AEL.
- Experiment execution and cross-run comparison stay in Q-Batch.
- The Differential remains reference material only unless a separate, justified write is approved.

## Guardrails

- Do not call this the complete AEL runtime.
- Do not claim the live ChatGPT shared-project or hosted-chat behavior was reproduced. The fixture models an AEL-side context change only.
- Do not equate membership or a role label with approval permission.
- Do not claim a real local-model inference was run unless captured and verified.
- Do not infer who read or understood a message from presence alone.
- Do not delete old context versions or participant periods; retain their event history.
