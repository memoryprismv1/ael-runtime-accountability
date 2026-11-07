# AEL scope and controlled context reuse

**Status:** Author scope clarification recorded on 7 November 2026. This is an implementation-design note, not a replacement for or expansion of the author's source framework. Where an implementation convenience conflicts with this boundary, revisit the implementation.

## What AEL is for

AEL is primarily an **accountability mechanism**. It makes actions, decisions, alternatives, constraints, provenance, and changes in operating context more inspectable.

It has additional benefits: it can give users more optionality and thinking space by exposing choices, trade-offs, uncertainty, and relevant prior knowledge.

AEL may help someone reason about a process. It does not need to own, operate, or manage the entire process.

A workflow can be an object AEL observes. AEL is not thereby the workflow manager.

## What AEL should not take ownership of

Do not turn AEL into:

- an end-to-end workflow orchestrator or project-management system;
- an organisation's identity, access-control, or permission-administration service;
- the authority that appoints approvers or decides who is entitled to make an organisational decision;
- a service that automatically distributes every context item into every related chat or project;
- a system that treats its own enforcement decision as a substitute for preserving evidence.

AEL may record what a host system says was allowed, denied, approved, or changed. It should retain the source and distinguish observed facts, claimed authority, and inference. It should not silently assume ownership of those external decisions.

## Accountability is not workflow enforcement

### Presence, action, and authority are different facts

- **Participant:** who was included in a conversation or decision chain during a recorded period.
- **Actor:** who performed, or attempted, a particular action.
- **Authority:** what authority was claimed or exercised, and what evidence/source supports that attribution.
- **Recorder:** which system persisted the record.

Presence does not prove reading, comprehension, notification, permission, or culpability. A role label such as `manager` or `approver` does not prove authority.

The purpose of these distinctions is to make the chain inspectable, not for AEL to run the chain.

### Review of the PR #32 membership gate

PR [#32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32) introduced a runtime check that rejects canonical event appends by an explicitly identified human/AI actor who is not in an active participation period. It also checks branch proposals before creating branch rows.

That check is now **under design review**.

An accountability mechanism should be careful not to discard the very evidence it exists to preserve. An action attempted by someone outside the recorded participation period may be an important discrepancy. Rejecting it before recording anything can hide that attempt.

The next design decision is whether AEL should instead preserve an attributed attempt and mark its relationship to the recorded participation history (for example, as outside the recorded period), leaving any operational permission decision to the host. Do not expand the membership gate into a general workflow access-control system until this question is resolved.

This review does not erase the existing participant periods or change the merged code. The current implementation remains as-is until a separately tested change is made.

## Supporting operations: complete the record, not police the process

Memory review, memory disposition, revision decisions, checkpoints, branch actions, and other supporting operations can affect what AEL retains or presents.

The remaining task is to ensure those operations have adequate attribution and evidence: who initiated them, what changed, when, under what recorded authority, and which object/version was affected.

The goal is **no accountability blind spots** across AEL's own mechanisms. It is not to impose a universal membership or approval rule on every external workflow. AEL should record an attempted or rejected action where possible rather than making evidence disappear.

## Controlled context reuse: reduce repeated discovery without indiscriminate sharing

The context problem is not primarily "how do we synchronise every chat?" It is "how can a new, similar project benefit from what has already been learned, without exposing information it should not receive?"

For an organisation running similar projects, useful knowledge may already exist elsewhere. A new project should not have to rediscover every method, tool, obstacle, or lesson from the ground up.

But similarity does not make two projects identical, and organisational ownership does not mean every participant or project is entitled to see every piece of information.

### Distinguish kinds of context

1. **Generally reusable organisational knowledge:** established methods, common procedures, templates, tools, and lessons deliberately made available beyond one project.
2. **Potentially reusable project learning:** an approach, result, mistake, or lesson learned in one project that may help another when its conditions and limitations are understood.
3. **Project-sensitive context:** client/person data, budgets, negotiations, credentials, private decisions, unpublished results, and other material that must remain in its authorised project boundary unless an authorised person explicitly permits a suitable form of reuse.

A lesson derived from sensitive work may sometimes be reusable in an abstracted or redacted form even when its original data, transcript, or documents are not. That must be a deliberate transformation and review, not an automatic assumption.

### Preferred shape: pull useful knowledge with provenance

The intended direction is **controlled, selective reuse**, not blanket propagation:

- A new project can discover that relevant prior knowledge may exist.
- The user can inspect its source, scope, age/version, conditions, and limitations.
- The user can choose to reuse an appropriate item, rather than importing an entire old conversation.
- The record preserves where the knowledge came from, which version was selected, why it was considered applicable, and what entered the new model context.
- The target project remains free to reject or revise the inherited advice. Similarity is a reason to consider reuse, not proof that it applies.

Useful context should carry enough information to avoid turning a past project's local conclusion into an unqualified universal rule: source, origin scope, version/hash, applicability conditions, sensitivity/reuse restriction, and any review or selection decision.

### Confidentiality and authorisation

Context scope and permission are separate questions.

- A project-specific item should not become broadly reusable merely because it is stored in an account-level database.
- AEL's current account/project scope fields are not a complete organisation ACL or confidentiality enforcement system.
- The host platform or organisation remains responsible for authenticating users and enforcing access to source material.
- AEL should record the source and reuse decision and, where available, the exact item/version included in model input.
- Do not automatically copy whole transcripts or sensitive source material between projects.
- Do not use the current plain-text context-intervention storage path for sensitive project content until appropriate access control, encryption, retention, and deletion protections exist. The current function stores the supplied content in the append-only SQLite event record.

## How this relates to existing AEL mechanisms

The existing memory pipeline already has useful pieces: source-linked candidates, visible review, a separate keep/use decision, account/project scopes, and applicability tags. Evaluate whether those mechanisms are sufficient for controlled reuse before adding a new context-sharing subsystem.

The existing `context.intervened` event can help record that a context resource/version changed within a conversation and what was used. It is **not** a cross-chat propagation service and should not be expanded into one by default.

A future adapter may retrieve an authorised, selected item from a host-managed source and record its provenance and model-input use in AEL. That is a possible integration boundary, not a reason for AEL itself to manage projects or distribute permissions.

## Practical test to guide design

Use synthetic, non-sensitive examples first:

- Project A records a method and a lesson learned, with source and applicability conditions.
- Project B is similar but not identical.
- Project B can discover the reusable lesson without being given Project A's private transcript or raw project data.
- A user selects whether the lesson is relevant.
- AEL records what was selected, its source/version, and whether/how it influenced the target model input.
- A deliberately sensitive item remains unavailable to Project B.

A successful design reduces repeated discovery while preserving project boundaries and user choice.

## Carry-forward decisions

1. Reassess PR #32's active-membership rejection gate against the accountability-first purpose; preserve evidence of attempted out-of-period actions where feasible.
2. Complete actor/provenance receipts for supporting AEL operations without turning them into a global workflow policy engine.
3. Treat cross-project work as controlled context reuse, not automatic cross-chat propagation.
4. Inspect and extend the existing memory pipeline before proposing another subsystem.
5. Keep confidentiality and access enforcement with the host/organisation; AEL records the relevant origins, decisions, and context actually used.
