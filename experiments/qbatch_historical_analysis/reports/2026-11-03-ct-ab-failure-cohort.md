# Q-Batch historical cohort analysis

**Classification:** read-only retrospective analysis; not rerun authority.  
**Replayed against current reader:** 4 November 2026.

## Summary

- Original audit archives inspected: **4**
- Independent workflow attempts: **4**
- Run logs inspected: **8 / 8**
- Event chains and final event-stream checksums verified: **8 / 8**
- Referenced evidence artifacts independently re-hashed: **920**
- Read failures: **0**
- Eligible four-attempt diagnostic cohorts: **0**
- Raw source evidence modified: **No**
- Decision: **INCONCLUSIVE — no eligible cohort reaches the minimum**

## Current-reader replay

The current code at the Q-Batch historical-analysis branch was run against the four original GitHub Actions audit ZIPs after extraction of both A and B arms. The replay verified the event sequence, per-event hash chain, referenced evidence size and SHA-256, context snapshot binding where present, and final event-stream checksum. All eight logs passed integrity verification. The replay returned zero read failures and independently re-hashed 920 evidence references.

The same four distinct observable failure signatures were recovered. The old manifests remain readable, but the analyser correctly marks them ineligible for comparable-cohort diagnosis because they do not contain runner implementation revision, worktree cleanliness, and explicit capture-profile identity/hash. Those fields were not backfilled into historical evidence.

The source archives were not modified. Their GitHub artifact ZIP SHA-256 values at retrieval were:

| Workflow run | Artifact ID | ZIP SHA-256 |
|---|---:|---|
| [39592787189](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39592787189) | `12343806764` | `0482ab6ec6b762c8f1846389ba35d6ee0ec45159458a0393efcb71ed68d1868b` |
| [39597455540](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39597455540) | `12346300690` | `ae486cd157c04fc9a3b4cc440a06e8cfc9b4870d4c48f310149612dd608be838` |
| [39730856613](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/39730856613) | `12405213878` | `b21156b434dbf9bfe4321f3b7d0b248f9f68447a8b7499c2692083472b9b213d` |
| [41619488320](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41619488320) | `13225155704` | `74f85769613e274f0352f3d0339a4eaf9aa0e43860ccaf79c434550b9ee15599` |

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

- Schema/logger labels remained 1.0 / 0.1.0 while recorded event capabilities evolved. Recording profiles are inferred from observed evidence, not explicit producer identities.
- Absence of an event in an older recording profile is not evidence that the event did not occur.
- Historical manifests omit runner revision, worktree-clean state, and explicit capture-profile identity/hash. New CT A/B runs bind this provenance to `run_started`; historical evidence was not edited or backfilled.
- The analyser identifies observable failure signatures, not proven root causes.
- Four comparable independent failures are a minimum eligibility threshold, not a guarantee of statistical certainty.
- A rerun recommendation requires a targeted fix and a passing regression test, and still requires manual approval.
- No raw event stream or model prompt/response artifact is reproduced in this report. Original GitHub artifacts remain the evidence source.

**Conclusion:** The current reader is backward-compatible with all four original archives and verifies their evidence. The evidence supports no batch diagnosis and authorises no rerun.
