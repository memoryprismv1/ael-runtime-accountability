# CT Experiment Test Report

GitHub Actions is the validation source of record; no pass result is claimed in advance.
- Baseline unit and mock local-bridge tests are copied into this tree.
- CT tests cover skill integrity, approval order, case/plan hash binding, case-change invalidation, append-only audit records, evidence-backed verification and task CLI exposure.
- The root comparison harness validates each manifest, uses separate AEL_PATH and import paths, records individual test outcomes and compares shared tests.
- CI preserves JSON comparison reports for Python 3.11, 3.12 and 3.13.

No real Ollama inference is asserted. This harness compares deterministic software regressions, not semantic quality or superiority of CT case notes/plans. Live-model comparison needs fixed evaluation cases, a pinned model/configuration, isolated state and independent scoring.
