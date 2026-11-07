# AEL external context interventions

## Why this exists

A conversation's visible message transcript is not the entirety of the context presented to a model. A shared instruction, project setting, or context file can change while the messages already exchanged remain untouched. AEL needs to represent that as a separate, attributable event rather than pretending it was a new chat message.

This prototype records **chat-scoped** external context changes. It does not claim to connect to ChatGPT shared projects, a hosted workspace, or a file-upload service. A future host adapter must supply authenticated actor IDs and the source reference for the change.

## Event and versioning

The `record_context_intervention(...)` function appends a `context.intervened` event to the canonical AEL ledger. The event records:

- resource ID and type;
- caller-supplied version label;
- previous version and previous SHA-256, when one exists;
- SHA-256 of the exact new UTF-8 content;
- actor ID, authority, recorder, and source reference;
- the exact context text to be injected.

The context text is stored in the append-only event content. Do not place credentials, private keys, or other secrets in these records. The same data-handling limits documented in `SECURITY.md` apply; this is not encrypted secret storage.

A caller may pass `expected_previous_sha256` for optimistic concurrency. A mismatch is rejected so an update based on a stale version does not silently overwrite a more recent change. An unchanged content hash is treated as a no-op and rejected.

## Effect on model context

The ordinary message transcript is unchanged. The AEL event history gains a separate `context.intervened` record.

During hydration, only the latest intervention for each resource ID is included in active context. Older versions remain in immutable history and appear as superseded records in the projection. Active intervention content is protected during context packing: AEL does not silently truncate it. If protected context does not fit, the existing protected-overflow behaviour applies.

The model-input audit sidecar records the resource/version/hash metadata and actor/source attribution, while the provider-facing model input receives the bounded working context and current user message only. The sidecar itself is not sent to the model.

## API

```python
record = runtime.record_context_intervention(
    con,
    account="acct-1",
    project="project-a",
    chat="chat-a",
    resource_id="shared-approval-guide",
    resource_type="project_instruction",
    version="v2",
    content="Approvals require the named approver's explicit selection.",
    actor_id="org:example-company:user-123",
    authority="user_direct",
    source_ref="project-settings:approval-guide:v2",
    expected_previous_sha256="<previous-content-sha256>",
)
```

An identified human or AI actor must be an active participant in the chat (or in the matching workflow when the event is workflow-scoped). Explicit system/service actors follow their separate runtime path. Participation is not proof of approval permission: the `authority` value is recorded separately, and AEL does not yet implement a role/capability policy that independently grants approval rights.

## Current boundary

- Resource history and active-context selection are tested within one account/project/chat scope.
- Cross-chat/project-wide resource propagation is not implemented by this prototype.
- The code records that a context intervention occurred; it does not prove that a platform delivered the change to a particular model request. A real adapter should correlate the AEL event with the actual hydrated/model-input hash.
- `source_ref` is a reference supplied by the host; AEL does not authenticate the external source on its own.
