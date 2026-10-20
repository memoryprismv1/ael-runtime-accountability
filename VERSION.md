# Version

**Package:** AEL Runtime Prototype V2.8.1 — public review repository staging
**Scope:** Selected AEL V1 runtime primitives, post-expansion delta conformance, bounded model input, memory promotion/usage disposition, and optional loopback-only local Ollama chat.
**Latest local validation:** 57 unit tests, Python compilation, CLI smoke checks, and mock-server interactive-chat end-to-end tests passed in the development environment.
**Not included:** Direct ChatGPT/Claude website connection, cloud/provider APIs, real Ollama inference in the development environment, automatic model-weight learning, semantic truth validation, or production concurrency guarantees.

Read `README.md` first, then `SOURCES.md`, `DESIGN_ALIGNMENT.md`, `NEXT_STEPS.md`, `TEST_REPORT.md`, and `LOCAL_MODEL_BRIDGE.md`. Original AEL source documents are linked in `SOURCES.md`; internal source documents are not redistributed in this staging package.


## Candidate branch notice

The main branch remains V2.8.1. The feature branch \`feat/critical-thinking-task-precommitment-v2.9\` contains an experimental task-level precommitment workflow targeting V2.9.0. It must not be labelled a release until the full test suite, compatibility checks, and candidate limitations have been reviewed.
