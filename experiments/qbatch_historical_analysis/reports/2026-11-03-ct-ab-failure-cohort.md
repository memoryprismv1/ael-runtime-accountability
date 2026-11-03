# Q-Batch historical cohort analysis

**Classification:** read-only retrospective analysis; not rerun authority.

## Summary

- Runs inspected: **8**
- Independent workflow attempts: **4**
- Fully verified runs (event chain, referenced artifacts and checksum): **8 / 8**
- Evidence references independently re-hashed: **920**
- Committed analyser replay: **PASS** (8 runs read, 0 read failures)
- Sanitized failure-signature regression cases: **4 added**
- Eligible four-attempt cohorts: **0**
- Future-run provenance fields added: **capture profile ID/version/hash, runner revision, worktree-clean state**
- Decision: **INCONCLUSIVE — no eligible cohort reaches minimum**

## Replay verification

The committed analyser was executed against the four original GitHub Actions audit ZIPs after extracting both A and B arms. The replay verified each event chain, all referenced artifact sizes and SHA-256 hashes, each context binding where present, and each event-stream checksum. It produced the same four failure signatures recorded below, with 8/8 runs fully verified and 920 evidence references re-hashed. The raw archives were not modified. The short ZIP folder labels were mapped to their corresponding workflow run IDs only in the replay input directory.

## Run findings

| Workflow attempt | Arm | Observed recording profile | Failure signature | Diagnostic observation |
|---|---|---|---|---|
| [39592787189](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39592787189) | A and B | legacy model-exchange | text-encoded tool calls not dispatched | 24 JSON tool intents; zero dispatched calls in each arm |
| [39597455540](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39597455540) | A and B | legacy with tool dispatch | repeated no-tool responses | 21 no-tool responses and 3 dispatched calls in each arm |
| [39730856613](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39730856613) | A and B | legacy transport-failure | first-request timeout | Both arms failed on the first model request |
| [41619488320](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41619488320) | A and B | context and request lifecycle | rejected plan resubmission loop | 7 rejected repeat plans and 24 tool calls in each arm |

## Cohort results

| Failure signature | Independent attempts | Result |
|---|---:|---|
| text-encoded tool calls not dispatched | 1 | ineligible: missing comparability metadata |
| repeated no-tool responses | 1 | ineligible: missing comparability metadata |
| first-request timeout | 1 | ineligible: missing comparability metadata |
| rejected plan resubmission loop | 1 | ineligible: missing comparability metadata |

A and B are paired arms of one workflow attempt and count as **one** independent attempt, not two. The four attempts have four different failure signatures and therefore cannot be combined into a single diagnostic cohort.

## Interpretation limits

- The historical schema/logger labels remained 1.0 / 0.1.0 while recorded event capabilities changed. Recording profiles are inferred from observed evidence, not explicit producer identities.
- Absence of an event in an older recording profile is not evidence that the event did not occur.
- The old manifests omit the runner implementation revision, worktree-clean state, and explicit capture-profile identity/hash. Comparability metadata is incomplete even where task and model details appear similar. These fields are now recorded and bound to `run_started` for new CT A/B runs; the historical evidence was not modified or backfilled.
- The analyser identifies observable failure signatures, not proven root causes.
- Four comparable independent failures are a minimum eligibility threshold, not a guarantee of statistical certainty.
- A rerun recommendation requires a targeted fix and a passing regression test, and still requires manual approval.
- No raw event stream or model prompt/response artifact is reproduced in this report. Original GitHub artifacts remain the evidence source.

**Conclusion:** No batch diagnosis or rerun recommendation is authorised by this evidence.
