# AEL Runtime — Next Steps / Handoff

**Current build:** V2.8.1 — source-reconciled local prototype with retention/use policy, memory-promotion stages, delta-first delivery and conformance checking, bounded model context, an optional loopback-only Ollama adapter, and an interactive local chat shell.  
**Current phase:** Stabilisation of existing behaviour. No new features are in scope unless a minimal change is required to repair a demonstrated defect.  
**Latest recorded CI:** PR #22 run [#351](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41791081760), commit `740d6ef1e138898302169531c44d77d647ba883b`; Python 3.11, 3.12 and 3.13 jobs passed. Python 3.11 groups: 65 runtime/generic logger tests, 32 CT logging and paired-runner tests, 2 Q-Batch method tests, and 18 historical-analysis tests.  
**Ownership:** AEL and the source architecture belong to the user. This is an implementation handoff, not a new AEL specification.

## What V2.8.1 added

- Added `ollama-status` to check a loopback Ollama service and enumerate model names without sending a prompt or opening the AEL database.
- Added `ael_chat.py` and `START_AEL_CHAT.bat` for interactive multi-turn use; turns persist in the same append-only ledger. `/new` changes chat identity and isolates the next local context.
- Explicitly excludes model names ending in `:cloud`; this bridge is local-only and requires no paid API token.
- Added tests for model inventory, unsafe-host refusal, cloud-model refusal, interactive persistence, local audit sidecars, and new-chat isolation.
- Cleaned conflicting older descriptions about the model adapter's status.

## Stabilisation work

1. **Reproducible baseline:** continue running the existing test suite from clean checkouts and record exact commits, commands, runtime versions, and results. Treat one successful run as a baseline observation, not proof of production readiness.
2. **Existing artifact integration:** the runtime already uses a workspace-rooted file-backed reader that pins and hashes source bytes and revalidates them during expansion/verification. Existing tests cover changed/disappeared sources, exact CRLF bytes, path escapes, and same-rooted reads. This is implemented behaviour to preserve and stabilise, not an outstanding feature request.
3. **Existing persistence and migration:** retain the current append-only ledger, database-reopen, context rehydration, and legacy migration tests. Investigate and fix only reproducible failures in these contracts.
4. **Local model boundary:** the loopback-only Ollama adapter and interactive shell have mock-service coverage. A real local-model inference run remains unverified; it is not required to validate the current persistence, control-flow, or evidence contracts and is not part of this stabilisation cycle.
5. **Documentation accuracy:** keep this handoff and `ROADMAP.md` aligned with code and tests. Clearly distinguish implementation that is tested with mocks from behaviour verified against a real local model.

## Deferred — not part of the stabilisation phase

The following items would add or materially expand capabilities. Do not start them during the current stabilisation window:

- independent semantic conformance engine beyond the existing scope/conformance checks;
- automatic lesson extraction and candidate generation;
- memory walk-back decay/reactivation automation;
- a new UI/runtime bridge;
- any new storage or analytical subsystem.

Keep these ideas recorded as deferred possibilities, not active implementation tasks.

## Do not do

- Do not describe this as the complete AEL runtime.
- Do not claim a real local-model inference was run unless an actual run is captured and verified.
- Do not introduce a paid API requirement merely to test local persistence or control-flow mechanics.
- Do not treat source essays or the Evidence Pack as subordinate to implementation convenience.
- Do not infer source truth from model self-report.
- Do not delete retained history because a record is currently irrelevant.
- Do not expand a full artifact before the exact delta is explicitly accepted.
- Do not mark a candidate release-ready until structural conformance passes.
- Do not add new features during stabilisation to work around an uninvestigated defect.
