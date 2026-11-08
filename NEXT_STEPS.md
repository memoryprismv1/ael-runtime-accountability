# AEL Runtime — Next Steps / Handoff

**Runtime feature baseline:** `44561c1b10948e34e671b495d6fe486f89a0a2fc`  
**Latest merged feature:** PR [#35](https://github.com/memoryprismv1/ael-runtime-accountability/pull/35), multi-agent accountability fixture and portable skill-log example.  
**Current phase:** Evaluate portable team-skill building from accountable ledger evidence. Keep the first skill as a synthetic candidate; test the record format against a second, unrelated scenario before considering extraction automation.  
**Latest CI:** PR [#35](https://github.com/memoryprismv1/ael-runtime-accountability/pull/35), run [#462](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42467690594), passed 88 tests on Python 3.11, 3.12 and 3.13.

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

1. **Compare the two candidate records:** Review which fields are genuinely common and which may be optional or domain-specific. Two synthetic fixtures are only an initial compatibility check, not enough to declare a universal schema.
2. **Define the curation boundary:** Separate source evidence, generalised lesson, sensitive details that must be withheld, human review, validation and reuse status. Do not equate anonymisation with proof that a lesson is safe or universally applicable.
3. **Try one reviewed, non-sensitive real team lesson before automation:** A real example can expose details that synthetic cases cannot—source restrictions, contextual dependencies, redaction risk and whether the resulting skill is actually useful to another team. Keep the source history local and select only material explicitly suitable for reuse.
4. **Keep extraction manual for now:** The two examples in `examples/team-skill/` are manually curated candidates. Do not build an automatic extractor until the record has been tested against real curation and review needs.
4. **Controlled context reuse:** Continue to examine how a new project can selectively reuse reviewed skills without importing whole conversations or project-sensitive information.
5. **Attempt versus acceptance:** Review whether AEL should preserve and flag attributed action attempts outside a recorded participation period rather than reject them before an accountability record exists.
6. **Supporting-operation evidence:** Review memory lifecycle, revision decisions and checkpoints for complete actor/source/version receipts. This is accountability coverage, not global workflow enforcement.
7. **Host boundary:** The host/organisation remains responsible for authentication, access control and retrieval permissions. AEL records origins, choices and model-context use; it does not administer organisation permissions.

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
