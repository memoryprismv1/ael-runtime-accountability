# Critical review: actor identity, event classification and authority skill

**Review date:** 8 November 2026  
**Candidate:** `examples/team-skill/actor-provenance-authority-separation.json`  
**Source:** AEL PR [#35](https://github.com/memoryprismv1/ael-runtime-accountability/pull/35), merge commit `44561c1b10948e34e671b495d6fe486f89a0a2fc`  
**Review status:** Critical scope review completed. Human/team adoption review remains pending.

## Decision

Keep the candidate, but narrow its claims. The transferable lesson is real: when a shared message path gains new kinds of speakers, assumptions built for the original speaker type must be examined explicitly. The skill must not imply that a roster label authenticates a speaker or confers authority.

## Findings and corrections

### 1. The source was a fixture path, not the whole ledger

The code correction is in `ael/multiuser_fixtures.py`, inside the deterministic CSV fixture runner's `message` action. It does not demonstrate that the core ledger append API or a production host adapter applies the same mapping.

**Correction:** The candidate's provenance now identifies the deterministic fixture runner as its source scope.

### 2. Participant type was too closely associated with authority

The fixture's explicit mapping assigns a human participant `user_direct` authority. That is a convention used in this deterministic scenario. The code does not authenticate a human, check a host permission, or prove a real authorisation decision.

**Correction:** The skill says authority must be established separately from authenticated permissions or explicit delegation evidence. Participant type, membership, role, provenance and the ability to send a message are not sufficient. The fixture's `user_direct` default must not be copied as a production authority rule.

### 3. The mapping's provenance is fixture-specific

The fixture selects default provenance and claim classification using the registered participant type. That is an explicit mapping in this harness, not a universal rule that actor type alone proves how a message entered any receiving system.

**Correction:** The revised method asks a receiving team to inspect the fields it actually stores and resolve speaker identity from trusted host evidence. It tells the team to adapt classification to its real transport and source metadata, rather than copy AEL's mapping wholesale.

### 4. Fields not demonstrated were presented as though exercised

The first extraction called out represented principals and recorders as though PR #35 exercised them. It did not.

**Correction:** The revised skill limits its core method to the receiving system's actual persisted fields. It mentions an on-behalf-of relationship only conditionally, when the receiving system supports it and has evidence for it.

### 5. The test coverage was broader in the prose than in the scenario

The PR #35 multi-agent scenario asserts the human and agent cases. The mapping code contains service, system and unknown-speaker branches, but the scenario does not independently test all those branches.

**Correction:** This is recorded as a limitation. The portable method recommends testing every actor type the receiving integration claims to support, including fallback behaviour.

## Refined transferable practice

1. Enumerate the speaker types the integration actually supports.
2. Inspect the shared write path and list the attribution fields it actually persists.
3. Resolve speaker identity using trusted host evidence; do not treat a roster entry or fixture key as authentication.
4. Replace implicit human-only defaults with explicit mappings appropriate to the receiving system's evidence.
5. Establish authority separately from speaker type, role, membership or provenance.
6. Keep an acting agent/service distinct from a represented principal only where the relationship is evidenced and supported by the receiving data model.
7. Test expected mappings and prohibited substitutions through the actual write path.
8. Retest established human behaviour and compatibility.

## What this review does not certify

- Authentication or permission checks in a live hosted chat or multi-agent platform.
- Correct mapping for every service, system, tool or unknown actor.
- A production incident, incident rate or measured improvement.
- Universal applicability to every event model.
- Adoption by another engineering team.

The candidate is now more faithful to the actual source. Its critical scope review is complete, but human/team adoption review remains pending. A green AEL test suite validates the repository fixture and its assertions; it does not certify the extracted skill for general use.
