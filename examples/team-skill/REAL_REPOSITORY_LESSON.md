# Third portable-skill example: actor identity, event classification and authority

This candidate is distilled from a real AEL repository code correction. The source was a deterministic fixture runner, not a production service.

## What actually happened

When the multi-agent fixture was added, its shared `message` branch still applied human-only defaults to every speaker:

- user provenance;
- direct-user authority;
- user-statement classification.

That was no longer a sound description once separately identified agents could send messages through the same fixture path.

PR [#35](https://github.com/memoryprismv1/ael-runtime-accountability/pull/35) changed the fixture runner to resolve the registered speaker and select a mapping for the participant type. The integration scenario asserts that agent messages retain their own participant identity, use assistant provenance and do not receive human direct-user authority. It also checks that human messages and human branch decisions remain separately attributed.

## Critical review and corrections

The first extraction was broader than its evidence. This review found and corrected three overstatements:

1. **Fixture versus production:** The change is in `ael/multiuser_fixtures.py`. It does not demonstrate that the core ledger append boundary or a live hosted multi-agent adapter performs the same mapping.
2. **Speaker type versus authority:** The fixture still maps a `human` participant to `user_direct`. That is a deterministic scenario convention, not proof of authentication, permission or actual authorisation. The portable skill now explicitly warns receiving systems not to copy it as an authority rule.
3. **Fields not exercised:** The earlier extraction discussed represented principals and recorders as though they were demonstrated by this change. They were not. The revised skill limits its core method to fields actually present in the path and mentions on-behalf-of data only conditionally, where a receiving system explicitly supports it.

The PR #35 test scenario asserts the human and agent cases. Although the fixture mapping also includes service, system and unknown categories, that scenario does not independently test all those branches. The revised skill says so.

## Generalised practice

The transferable lesson is narrower and stronger:

**When a shared message or event path gains new kinds of speakers, replace implicit human-only defaults with explicit speaker-aware classification, and establish authority separately from speaker type.**

For another team, this means examining its actual writer and fields, using the host's trusted identity evidence, separating event source from authority, and writing positive and negative tests through the real receiving path. A registry label or role is not authentication; a speaker's ability to send a message is not permission to perform every action.

## Provenance and review status

The machine-readable skill points to the public AEL repository, PR, commit, changed source files and the relevant integration test. It excludes participant names/IDs, account/project/chat identifiers and raw conversation text. The source scope is explicitly labelled as the deterministic fixture runner.

This is a real repository implementation correction, not a production incident. The critical scope review has been completed, but the extracted practice remains a candidate pending your or another team's adoption review. The code tests validate the fixture correction; they do not certify the skill for general use.
