# Retention Is Not Relevance — Usage Disposition (V2.5)

**Status:** Implemented prototype rule, added after a user correction grounded in the AEL / *Learning the World Through Others* line of thought. This file documents an implementation interpretation; it does not amend or replace the user's source documents.

## Core distinction

**Keep the data. Govern its use separately.**

An outcome can change whether a piece of information should influence the current work without making the historical information worthless or eligible for deletion. Failed alternatives, corrections, cues and candidate lessons remain stored with their source and history. The runtime assembles only the information allowed to influence a particular context.

Retention, lifecycle stage, factual truth, decision authority, and current-use disposition are separate dimensions. None should be silently substituted for another.

## Materiality: ambiguity is not automatically a branch

The Materiality Gate asks whether a choice made on the user's behalf materially determines what happens next. Difficulty or ambiguity by themselves are not sufficient reasons to expose formal branches.

- **Single path:** context makes the interpretation clear, or the request has no material decision boundary. Execute directly.
- **Cheap clarification:** if a low-cost ambiguity genuinely needs resolving, use contextual clues or ask one concise question. Do not turn ordinary word-sense clarification into a full A/B/C process.
- **Formal branch exposure:** use only when materially different paths carry consequences that should be visible before expensive work starts.
- **Recommend:** when the user wants the agent's recommendation but retains authorization.
- **Overrides remain available:** the user can request branching or tell the agent to pick and proceed.

### Example: “Lancet”

If surrounding context clearly identifies *The Lancet* journal, proceed with that interpretation. If context is insufficient, a brief question such as “The medical journal The Lancet?” is enough. The alternatives—journal, surgical instrument, other use—are not automatically a material strategic fork. The unused interpretation should not be deleted; its relevance is simply not active in the current task.

This example is a calibration test for the Materiality Gate, not a new domain-specific skill.

## Usage statuses

Every shared memory can carry a `usage_status` independently of its historical presence and lifecycle stage:

| Status | Meaning | Default influence |
|---|---|---|
| `use_when_relevant` | A human-ratified claim is useful when the current task actually matches its scope/tag. | Only with an explicit matching relevance tag, or the reserved `always` tag. |
| `never_try_again` | Preserve a negative lesson or rejected strategy as a constraint against repeating it. | Only when the exact tag/strategy key is explicitly relevant. |
| `maybe_later` | Keep available for future retrieval or reconsideration, but not for this context. | No automatic influence. |
| `not_pertinent_now` | Keep the information, but it is not relevant to the current context. | No automatic influence. |

The tag acts as the explicit applicability key in this prototype. The runtime does not claim to solve general semantic relevance automatically. A future connector must supply relevant tags or use the explicitly opted-in `always` tag.

## Branch outcomes

A rejected branch is not deleted. Its complete artifacts remain in the event ledger; the active projection excludes the rejected output so it cannot anchor the immediate retry. A separate usage label is recorded:

- `not_pertinent_now` by default: rejected for this attempt, without claiming the idea can never be useful;
- `maybe_later`: retain for later reconsideration;
- `never_try_again`: explicit negative strategy rule, not inferred from rejection alone.

The branch's usage label and rejection reason remain visible in the control record. The rejected artifact itself stays out of model-facing context. A strategy-wide, cross-session rule should be captured as a memory candidate and pass through the normal visible review and ratification steps; it is never promoted automatically from a single rejection.

## Memory promotion and retention

1. A source event supports a local candidate.
2. The candidate can be accepted, edited or declined. Declining does not delete it; it remains local and can be reopened later.
3. Acceptance/edit creates a shared read-only reference. It is still not an instruction.
4. The user assigns a use disposition: use when relevant, avoid this strategy, maybe later, or not pertinent now.
5. Only `use_when_relevant` and `never_try_again` with the appropriate approval and applicability can influence model-facing context.
6. A future context can change the disposition while the original claim, source and transition history remain available.

Legacy API calls that used `discard` are mapped to `not_pertinent_now` in the internal compatibility layer. They do not delete the row. The new user-facing CLI omits a discard action.

## Relation to the source corpus

*Learning the World Through Others* treats learning as an ongoing loop of remembering, testing, observing outcomes, updating and propagating information, while warning that cues can become stale or misleading as conditions change. This implementation draws an engineering distinction from that frame: **outcome informs use; it does not erase the data**.

The four status labels and exact context-injection rules are implementation choices. They should be tested against actual failures and can be revised without rewriting the historical event record.

## Acceptance tests

- Low-materiality ambiguity does not trigger a formal branch.
- Every rejected branch artifact remains in the historical ledger.
- `not_pertinent_now` and `maybe_later` never enter model-facing context automatically.
- `never_try_again` enters only on a matching explicit tag.
- A use-status change is recorded as a separate event and does not rewrite the source event.
- Declined local memory candidates remain local, retrievable, and reopenable.
- No new workflow deletes information in order to mark it non-current.
