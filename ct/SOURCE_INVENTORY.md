# Source Inventory and Provenance

This repository contains a working implementation prototype and engineering notes. The AEL source framework remains the author's work and the authoritative source for the concepts being implemented.

## Public AEL source sequence

The original source pages are linked in [`SOURCES.md`](SOURCES.md). They are referenced by URL rather than copied into this repository.

## Supporting materials used during development

The development process used the author's AEL Runtime Accountability V1 document, technical Design Notes, and V1 Evidence Pack. The supporting files are not redistributed in this public code bundle. See the author's original public pages for the authoritative framework and [`EVIDENCE_RECONCILIATION.md`](EVIDENCE_RECONCILIATION.md) for the engineering team's source boundary.

## Included implementation and test materials

- `runtime.py` — local event ledger and runtime primitives.
- `ael_chat.py` — interactive local chat shell.
- `tests/` — unit and mock-server integration tests.
- `DESIGN_ALIGNMENT.md` — status of the implemented mechanisms and gaps.
- `CONTEXT_BUDGET_POLICY.md`, `MODEL_INPUT_BOUNDARY.md` — active context and model-input controls.
- `MEMORY_WORKFLOW.md`, `USAGE_DISPOSITION.md` — candidate memory promotion and retention/use distinction.
- `DELTA_FIRST_DELIVERY.md` — delta proposal, decision, reset and conformance workflow.
- `LOCAL_MODEL_BRIDGE.md` — optional local Ollama adapter.
- `TEST_REPORT.md` — reproducible local test status.

Historical internal audit files are retained when useful to understand implementation decisions. They do not supersede the original AEL source documents.
