# AEL Runtime — Next Steps / Handoff

**Current main:** `301fb4bec68829460509851d83d2e225a859faad`  
**Current phase:** Preserve the accountability-first scope; examine the action gate; explore controlled reuse of prior knowledge.  
**Latest CI:** PR [#32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32), run [#445](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42377856668), passed 85 tests on Python 3.11, 3.12 and 3.13.

## Scope clarification — 7 November 2026

See [AEL_SCOPE_AND_CONTEXT_REUSE.md](AEL_SCOPE_AND_CONTEXT_REUSE.md). AEL is primarily an **accountability mechanism**, with additional benefits of giving the user optionality and thinking space. It may help people reason about a workflow; it does not own or manage the workflow. Record and expose evidence; do not become the workflow orchestrator, organisation access-control service, or automatic context-distribution service.

### Important review: PR #32's membership gate

The merged implementation rejects identified human/AI actors who append canonical events outside an active participation period. This is now **under design review**, not an unquestioned target to extend. An attempted action outside the recorded participation period may itself be accountability evidence. The current rejection gate could hide that attempt if it leaves no record.

Review whether AEL should record an attributed action attempt and flag its relationship to the participation history, instead of policing the workflow by refusing to record it. Do not expand this into general workflow enforcement before resolving that question. Existing code remains unchanged pending a separate tested decision.

## Merged and recorded

- [PR #30](https://github.com/memoryprismv1/ael-runtime-accountability/pull/30) — multi-user participant registry and actor attribution. Merge commit: `1eb82061768f2b9a84a1e6f066bc3d64c3792406`.
- [PR #31](https://github.com/memoryprismv1/ael-runtime-accountability/pull/31) — CSV participant roster importer and simulated multi-party scenario. Merge commit: `292fc42bcd7e0f4c930391fe69da17e910072c67`. The fixture is a test of attribution and presence, not an AEL workflow-management product.
- [PR #32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32) — canonical active-membership check and chat-scoped context intervention. Merge commit: `301fb4bec68829460509851d83d2e225a859faad`. CI [#445](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42377856668): 85 tests on all three Python versions.

## Next design work

1. **Evidence across supporting operations:** Review memory lifecycle, revision decisions, checkpoints and other AEL operations for complete actor/provenance/source/version receipts. The purpose is to avoid accountability blind spots, not enforce a global workflow policy.
2. **Attempt versus acceptance:** Decide how AEL records attempted, rejected, unauthorised, or out-of-period actions without silently erasing evidence. Keep recorded authority separate from any host-system authorisation result.
3. **Controlled context reuse:** Investigate how a new, similar project can selectively reuse prior methods and lessons without importing entire old conversations or exposing project-sensitive material.
4. **Reuse and sensitivity boundaries:** Distinguish organisation-wide reusable knowledge, potentially reusable project learning, and project-sensitive information. Similarity does not prove applicability; company ownership does not imply universal access.
5. **Provenance on reused knowledge:** Preserve the source project/item, version/hash, applicability conditions, sensitivity/reuse restriction, selection decision, and whether/how it influenced the target model input.
6. **Host boundary:** The host/organisation remains responsible for authentication, access control and retrieval permissions. AEL can record origins, choices and model-context use; it should not administer organisation permissions or propagate every context item across chats.

## Reuse direction — prefer selective pull, not blanket propagation

A new project may discover that relevant prior knowledge exists. The user can inspect its origin, version, limitations and applicable conditions, then choose whether to bring an appropriate item into the new context. Prefer a reusable lesson or method over copying an entire transcript. Keep source-sensitive details inside their authorised project boundary; an abstracted lesson may be reusable only after deliberate review.

The existing memory pipeline already has source-linked candidates, visible review, distinct keep/use choices, project/account scopes and applicability tags. Inspect and extend those mechanisms before proposing another context-sharing subsystem.

The current `context.intervened` feature records a change to context within one chat. It is not a cross-chat synchronisation service. Cross-project context reuse is a separate question.

## Boundaries and guardrails

- AEL observes, records, exposes and helps reason about accountability; it does not run the workflow being observed.
- Membership, action, authority and evidence are separate facts.
- Do not treat a role label as proof of permission.
- Do not let an enforcement gate erase evidence of a relevant attempted action.
- Do not automatically distribute project context or copy entire conversations between projects.
- Do not treat the present account/project scope fields as a complete organisation ACL.
- Do not put sensitive project content into the current plain-text context-intervention store until appropriate access, encryption, retention and deletion protections exist.
- No real hosted ChatGPT behaviour or real-model inference is claimed.
- Q-Batch owns experiment execution and cross-run evidence. The Differential was not modified by PRs #30–#32.
