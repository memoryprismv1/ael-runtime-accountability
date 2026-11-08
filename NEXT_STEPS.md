# AEL Runtime — Next Steps / Handoff

**Runtime feature baseline:** `45688bdee538bb6f51a4fdd6c1400618554719ef`  
**Latest merged feature:** PR [#36](https://github.com/memoryprismv1/ael-runtime-accountability/pull/36), second portable-skill scenario and record-format compatibility test.  
**Current phase:** Test the portable record against a repository-derived engineering lesson. Three examples now share the same outer fields: two synthetic scenarios and one real code-path correction. The third candidate remains pending independent human/team review.  
**Latest merged CI:** PR [#36](https://github.com/memoryprismv1/ael-runtime-accountability/pull/36), run [#468](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42468770147), passed 89 tests on Python 3.11, 3.12 and 3.13.

## Scope clarification — 7 November 2026

See [AEL_SCOPE_AND_CONTEXT_REUSE.md](AEL_SCOPE_AND_CONTEXT_REUSE.md). AEL is primarily an **accountability mechanism**, with additional benefits of giving the user optionality and thinking space. It may help people reason about a workflow; it does not own or manage the workflow. Record and expose evidence; do not become the workflow orchestrator, organisation access-control service, or automatic context-distribution service.

### Important review: PR #32's membership gate

The merged implementation rejects identified human/AI actors who append canonical events outside an active participation period. This is now **under design review**, not an unquestioned target to extend. An attempted action outside the recorded participation period may itself be accountability evidence. The current rejection gate could hide that attempt if it leaves no record.

Review whether AEL should record an attributed action attempt and flag its relationship to the participation history, instead of policing the workflow by refusing to record it. Do not expand this into general workflow enforcement before resolving that question. Existing code remains unchanged pending a separate tested decision.

## Merged and recorded

- [PR #30](https://github.com/memoryprismv1/ael-runtime-accountability/pull/30) — multi-user participant registry and actor attribution. Merge commit: `1eb82061768f2b9a84a1e6f066bc3d64c3792406`.
- [PR #31](https://github.com/memoryprismv1/ael-runtime-accountability/pull/31) — CSV participant roster importer and simulated multi-party scenario. Merge commit: `292fc42bcd7e0f4c930391fe69da17e910072c67`. The fixture is a test of attribution and presence, not an AEL workflow-management product.
- [PR #32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32) — canonical active-membership check and chat-scoped context intervention. Merge commit: `301fb4bec68829460509851d83d2e225a859faad`. CI [#445](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42377856668): 85 tests on all three Python versions.
- [PR #34](https://github.com/memoryprismv1/ael-runtime-accountability/pull/34) — simplified participant roster `type` to optional `human` or explicit `agent`, retaining internal AEL identity categories. Merge commit: `ffa7ebcd964cb2f9145b06f452ea9df7179a83c5`.
- [PR #35](https://github.com/memoryprismv1/ael-runtime-accountability/pull/35) — four-agent accountability scenario, speaker-aware provenance, human decisions, independent validation and anonymised portable skill-log example. Merge commit: `44561c1b10948e34e671b495d6fe486f89a0a2fc`. CI [#462](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42467690594): 88 tests on all three Python versions.

## Next design work

1. **Review the repository-derived skill:** Check whether the generalisation is faithful to the PR #35 code change and whether the method is useful outside the AEL fixture. The candidate is explicitly marked pending independent human/team review.
2. **Compare provenance needs:** Synthetic lessons point to fixture files and step numbers; a real engineering lesson points to a public repository, PR, commit, files and tests. Preserve this flexibility without weakening source traceability.
3. **Inspect the 14 shared top-level fields:** Three lessons now fit the same outer shape, but this is still a small sample. Identify fields that are truly universal and distinguish required fields from domain-specific detail.
4. **Keep extraction manual:** Do not build an automatic extractor yet. First test a human review and approval path on a real, non-sensitive lesson, including who can approve reuse and what happens when the candidate is revised or rejected.
5. **Controlled context reuse:** Continue to examine how a new project can selectively reuse reviewed skills without importing whole conversations or project-sensitive information.
6. **Attempt versus acceptance:** Review whether AEL should preserve and flag attributed action attempts outside a recorded participation period rather than reject them before an accountability record exists.
7. **Supporting-operation evidence:** Review memory lifecycle, revision decisions and checkpoints for complete actor/source/version receipts. This is accountability coverage, not global workflow enforcement.
8. **Host boundary:** The host/organisation remains responsible for authentication, access control and retrieval permissions. AEL records origins, choices and model-context use; it does not administer organisation permissions.

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
