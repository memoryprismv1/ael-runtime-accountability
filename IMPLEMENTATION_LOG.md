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


## 7 November 2026 — Accountability-first scope and controlled context reuse

**Reason for clarification:** AEL was drifting in implementation discussion toward managing workflows and distributing context between chats. The author clarified that AEL is primarily an **accountability mechanism**, with additional benefits of providing the user more optionality and thinking space. AEL may help examine workflows; it does not own or manage them.

**Design correction:**

- Recast participant identity, actor attribution and authority as separate accountability facts. Do not assume membership or a role label grants permission.
- Put PR #32's active-membership rejection gate under design review. An attempted action outside the recorded participation period can itself be evidence; rejecting it before creating an accountability record may conceal it. No code rollback or change was made as part of this documentation update.
- Reframe supporting-operation work as complete attribution and provenance receipts for AEL's own actions, not as a mandate to enforce external workflow policy.
- Reframe cross-chat context propagation as **controlled context reuse**: a new similar project can selectively reuse an applicable method or lesson from prior work, with source, version/hash, applicability conditions, sensitivity boundary and user selection recorded.
- Prefer selective retrieval of reusable knowledge over importing whole prior conversations. Keep project-sensitive information within the host/organisation's authorised scope. Organisation ownership does not imply universal project access.
- Inspect the existing memory candidate/review/use pipeline before proposing a new context-sharing subsystem.

**Document:** [AEL_SCOPE_AND_CONTEXT_REUSE.md](AEL_SCOPE_AND_CONTEXT_REUSE.md). This is an implementation-design clarification, not a new AEL framework specification. No runtime code, Q-Batch files or Differential files were changed by this clarification.


## 7 November 2026 — PR #33: accountability-first scope clarification

**Merge commit:** `95cec7e2f7236d66a65d7e0851a3528a980fb37f`

**Changed:** Added [AEL_SCOPE_AND_CONTEXT_REUSE.md](AEL_SCOPE_AND_CONTEXT_REUSE.md) and aligned the README, roadmap, handoff, participant-ledger notes and context-intervention guide.

**Recorded boundary:** AEL provides accountability, optionality and thinking space; it does not manage end-to-end workflows or administer organisational permissions. PR #32's active-membership rejection gate is under design review because an out-of-period action attempt may itself be evidence worth preserving. Cross-project work is framed as controlled, selective reuse of applicable knowledge with provenance and sensitivity boundaries, not blanket context propagation.

**Verification:** Documentation-only PR [#33](https://github.com/memoryprismv1/ael-runtime-accountability/pull/33), workflow run [#455](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42394886609), passed the existing 85-test suite on Python 3.11, 3.12 and 3.13. No runtime code changed.


## 8 November 2026 — PR #34: simple human/agent participant roster type

**PR:** [#34](https://github.com/memoryprismv1/ael-runtime-accountability/pull/34)

**Why:** The example participant roster required the internal `participant_type` vocabulary, even though the roster only needs to distinguish humans from agents. This made the list unnecessarily cumbersome and exposed runtime-specific categories to fixture authors.

**Changed:** Added an optional `type` column accepting only `human` or `agent`. Blank values and an omitted column default to `human`; agents must be explicitly marked `agent`. The importer maps `agent` to the existing internal `ai_agent` value so the database's system/service/unknown distinctions remain intact. Legacy `participant_type` CSVs remain accepted; specifying both columns is rejected as ambiguous. Updated the example roster and fixture documentation.

**Verification:** PR CI [run #459](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42466162643) passed 87 tests on Python 3.11, 3.12 and 3.13. Tests cover blank/default human, omitted column, explicit agent mapping, invalid values rejected before any identity is written, and the mixed participant example.

**Boundary:** This changes roster representation and fixture import only. It does not change identity authentication, membership, authority, action attribution or workflow behavior.


## 8 November 2026 — PR #35: multi-agent accountability scenario and portable skill example

**PR:** [#35](https://github.com/memoryprismv1/ael-runtime-accountability/pull/35)

**Why:** The existing multi-user fixture had one agent and recorded every message as a user statement. That could not demonstrate a team with distinct agent contributions, disagreement and review, or produce a useful example of generalised knowledge that could travel without the project transcript.

**Changed:**

- Expanded the deterministic roster to four humans and four explicitly typed agents: analysis, review, implementation and validation.
- Made fixture message attribution speaker-aware. Human messages retain user provenance and direct-user authority; agent messages retain assistant provenance and no human decision authority. Each agent has its own participant identity.
- Expanded the scenario to 27 steps. A reviewer challenges the initial analysis; two agent-authored alternatives are recorded; a human selects a prototype for evaluation; independent validation finds a boundary defect; the human rejects that approach; a revised proposal is selected, implemented and independently validated; the human records completion.
- Kept a passive manager who joins after the initial problem statement, remains present during the decision chain, and never acts. The requester leaves and rejoins under the same participant identity.
- Added [the portable skill-log example](examples/team-skill/portable-skill-log.json). It distils a boundary-checking lesson from the synthetic ledger scenario, retaining applicability, method, limitations, validation status and source fixture step references while omitting participant names/IDs, account/project/chat identifiers and raw conversation text.
- Added documentation and tests for separate agent attribution, human decisions, disagreement, validation, passive presence, re-entry and identity-free skill output.

**Verification:** PR CI [run #462](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42467690594) passed 88 tests on Python 3.11, 3.12 and 3.13.

**Boundary:** The scenario is deterministic and synthetic; it does not simulate independent model cognition or a live multi-agent host. The skill file is manually curated, not automatically extracted, and is validated only within this fixture. It is a candidate for reuse, not a universal rule. No workflow permission system or organisation ACL was added.


## 8 November 2026 — PR #36: second portable-skill scenario

**PR:** [#36](https://github.com/memoryprismv1/ael-runtime-accountability/pull/36)

**Why:** A single example could overfit the portable skill record to one engineering/process lesson. A materially different scenario was needed to test whether the same record structure could carry a different class of team learning without flattening its meaning.

**Changed:**

- Added a separate clean-database fixture for source-grounded evidence synthesis, with one human requester, one human decision-maker and four distinct agents for research, counterevidence, synthesis and verification.
- Used two synthetic source statements with different measures, coverage and comparison periods. The agents identify that apparent disagreement does not establish a directly comparable trend or cause.
- Recorded a proposed combined causal narrative, the human's rejection of that interpretation, a source-separated alternative, independent wording verification, and human completion.
- Added [a second portable skill candidate](examples/team-skill/source-grounded-claim-reconciliation.json). It uses the same 14 top-level fields as the chunk-boundary candidate but contains a different problem pattern, method, applicability and limitations.
- The portable record omits participant names/IDs, account/project/chat identifiers and the scenario's source-specific percentages. Source file and step references are retained for traceability to the synthetic evidence.
- Added tests for isolated database execution, speaker attribution, agent/human provenance, human decisions, identity/scope/number exclusion and top-level record compatibility. Updated the skill examples README and repository documentation.

**Verification:** PR CI [run #468](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42468770147) passed 89 tests on Python 3.11, 3.12 and 3.13.

**What this establishes:** The same outer record fields can express two different lessons from two synthetic scenarios. It is a compatibility signal for the current examples, not proof of a complete or universal skill schema.

**Boundary:** Both source scenarios are synthetic and each skill is validated only within its own fixture. The extraction remains manual. No automatic extractor, organisation-wide distribution service, permission system or real-world evidence-quality claim was added.


## 8 November 2026 — PR #37: portable skill from real actor-attribution correction

**PR:** [#37](https://github.com/memoryprismv1/ael-runtime-accountability/pull/37)  
**Merge commit:** `b0984e4231d41ccd08db2ce933fda7a52c69dfd4`

**Why:** After two synthetic examples, a third lesson was needed from an actual engineering change to test the portable format against real repository provenance and test evidence.

**Source experience:** Before PR #35, the shared fixture `message` path applied human-only defaults—user provenance, direct-user authority and user-statement classification—to every speaker. Adding agents made that mapping incorrect. PR #35 corrected the path to resolve the registered speaker and map the event fields appropriately.

**Changed:**

- Added [`actor-provenance-authority-separation.json`](examples/team-skill/actor-provenance-authority-separation.json), a portable candidate advising teams to trace actor identity, provenance and authority through shared event-writing paths when adding actor types.
- Preserved public source provenance: repository, PR #35, merged commit, source files and test names. Excluded participant names/IDs, account/project/chat identifiers and raw conversation text.
- Explicitly marked the skill as `tested_in_originating_repository_pending_skill_review` with `pending_independent_human_review_before_adoption`. Passing code tests is not approval of the extracted lesson.
- Added tests that compare the new record's 14 top-level fields with both existing skill examples, validate its source references and exclusions, and check its pending-review status.
- Updated the portable-skill guide, repository README and handoff.

**Verification:** PR CI [run #478](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42469697312) passed 90 tests on Python 3.11, 3.12 and 3.13.

**Boundary:** This is a real AEL repository engineering correction and code/test evidence, not a production incident or live hosted-platform integration. The extraction is pending independent human/team review. It does not add an automatic extractor, permission system or organisation-wide distribution mechanism.
