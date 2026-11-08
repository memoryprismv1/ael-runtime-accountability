# Third portable-skill example: actor, provenance and authority

This example is distilled from a real engineering change in the AEL repository, rather than a synthetic workflow.

## Source experience

When the multi-agent fixture was added, its shared `message` path still used human-only defaults: user provenance, direct-user authority and user-statement classification. That was harmless while every speaker in the fixture was human, but wrong once separately identified agents could send messages through the same path.

PR [#35](https://github.com/memoryprismv1/ael-runtime-accountability/pull/35) corrected the path to resolve the registered speaker and map the event fields appropriately. The accompanying tests assert that agent messages retain their own actor identity and assistant provenance and do not acquire human direct-user authority, while human messages and decisions remain separately attributed.

This was a real repository implementation issue found and corrected during development. It was not a production incident, and it is not evidence that a live multi-agent host has been integrated.

## Generalised skill

[`actor-provenance-authority-separation.json`](actor-provenance-authority-separation.json) turns that experience into a reusable review method: when adding actor types to a shared event path, trace all attribution fields and test both correct mappings and forbidden substitutions.

The skill is intentionally careful about boundaries. Participant type is not authentication. Membership is not permission. A role label is not authority. The host must provide trusted identity and delegation evidence.

The extracted skill remains a candidate. Its validation evidence is drawn from the merged code change and repository tests, but the extraction itself is marked as pending independent human/team review before adoption.

## Provenance and privacy

The skill points to the public AEL repository, PR, commit and source files so its origin can be checked. It does not contain participant names, participant IDs, account/project/chat scope IDs or raw conversation text.

This provenance is intentionally different from the two synthetic examples. The source is a real code change with a merged implementation and test evidence, not a numbered synthetic conversation. The common top-level skill record remains the same.

## Validation boundary

- The change and its tests were exercised in the AEL repository.
- CI passed 88 tests across Python 3.11, 3.12 and 3.13 after PR #35.
- No live hosted platform or production multi-agent environment was tested.
- The lesson is a candidate engineering practice, pending independent human/team review. Its use elsewhere still requires mapping the fields to that system's actual identity, provenance and authority model.
