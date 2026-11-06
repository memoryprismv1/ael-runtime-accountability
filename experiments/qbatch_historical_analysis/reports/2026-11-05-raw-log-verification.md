# Q-Batch raw run-log verification — 5 November 2026

Four paired attempts were recovered from GitHub Actions: 8 run logs, 1,038 events, and 920 referenced evidence files.

| Workflow attempt | A events | B events | A errors | B errors |
|---|---:|---:|---:|---:|
| 39592787189 | 127 | 127 | 25 | 25 |
| 39597455540 | 135 | 135 | 22 | 22 |
| 39730856613 | 8 | 8 | 2 | 2 |
| 41619488320 | 249 | 249 | 1 | 1 |

**Integrity:** 8/8 event streams match their checksum files; 8/8 event hash chains pass; 920/920 referenced evidence files match their recorded size and SHA-256; no references are missing.

**Status:** all eight runs ended with `completion_status=failed`; all four paired reports say `RUN_INCOMPLETE`.

These records support basic descriptive reports: event counts, event types, timestamps, phase/tool activity, observed errors, completion status, and integrity checks. They do not establish that A or B is better, causal effects, general model efficacy, or recurring root causes. The four attempts have different observable failure signatures, so there is no eligible repeated-failure cohort. A and B are paired arms; count four attempts, not eight independent experiments.

Raw run manifests, event streams, checksum files, pair reports and task manifests are packaged in the companion archive. The full original Actions ZIPs, including referenced evidence, are retained in the companion preservation ZIP linked from the inventory record.