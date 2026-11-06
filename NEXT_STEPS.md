# AEL Runtime — Next Steps / Handoff

**Current build:** V2.8.1 — source-reconciled local prototype with retention/use policy, memory-promotion stages, delta-first delivery and conformance checking, bounded model context, an optional loopback-only Ollama adapter, and an interactive local chat shell.  
**Current phase:** Final stabilisation closeout of existing behaviour. No new features are in scope unless a minimal change is required to repair a demonstrated defect.  
**Historical pre-split CI baseline:** [run #388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810) passed 132 combined AEL/Q-Batch tests per Python version. On 6 November 2026 the repositories were separated: AEL now runs its 69 runtime/mock-bridge tests; Q-Batch owns its own logger, harnesses and experiment CI. The first post-split AEL workflow run will establish the current CI baseline.  
**Ownership:** AEL and the source architecture belong to the user. This is an implementation handoff, not a new AEL specification.

## Stabilisation closeout — 5 November 2026

- The clean-checkout baseline above is confirmed on all three Python versions. The latest code change under test adds only deterministic SQLite failure-injection coverage: a rejected event insert leaves no phantom row, a later valid append succeeds, and the append survives a database reopen. No runtime feature was added in that commit.
- Q-Batch historical-analysis PR [#22](https://github.com/memoryprismv1/ael-runtime-accountability/pull/22) was merged on 4 November 2026 (merge commit `b87cb320cc53e59357fd334fbdd8b46fab899a2f`). There are currently zero open pull requests.
- One separate issue remains open: [#1 — Preserve independent assessor ratings in CT evaluation](https://github.com/memoryprismv1/ael-runtime-accountability/issues/1). It expands the scorecard schema and remains outside this stabilisation scope.
- The `main` branch is currently unprotected (no required status checks configured). This was observed and not changed as part of the documentation handoff.
- No real-model inference or CT pilot workflow was launched. The real-model workflow remains manual-dispatch only; routine CI is not pilot evidence.

## What V2.8.1 added

- Added `ollama-status` to check a loopback Ollama service and enumerate model names without sending a prompt or opening the AEL database.
- Added `ael_chat.py` and `START_AEL_CHAT.bat` for interactive multi-turn use; turns persist in the same append-only ledger. `/new` changes chat identity and isolates the next local context.
- Explicitly excludes model names ending in `:cloud`; this bridge is local-only and requires no paid API token.
- Added tests for model inventory, unsafe-host refusal, cloud-model refusal, interactive persistence, local audit sidecars, and new-chat isolation.
- Cleaned conflicting older descriptions about the model adapter's status.

## Stabilisation work

1. **Reproducible baseline:** continue running the existing test suite from clean checkouts and record exact commits, commands, runtime versions, and results. Treat one successful run as a baseline observation, not proof of production readiness.
2. **Existing artifact integration:** the runtime already uses a workspace-rooted file-backed reader that pins and hashes source bytes and revalidates them during expansion/verification. Existing tests cover changed/disappeared sources, exact CRLF bytes, path escapes, and same-rooted reads. This is implemented behaviour to preserve and stabilise, not an outstanding feature request.
3. **Existing persistence and migration:** retain the current append-only ledger, database-reopen, context rehydration, legacy migration, and checkpoint-export contracts. Repeated checkpoint exports now retain unique files matching each stored snapshot hash; project/chat identifiers are encoded to keep exports inside the selected directory. Regression tests pass in CI.
4. **Local model boundary:** the loopback-only Ollama adapter and interactive shell have mock-service coverage. A real local-model inference run remains unverified; it is not required to validate the current persistence, control-flow, or evidence contracts and is not part of this stabilisation cycle. The GitHub pilot is manual-dispatch only. Because the repository is public and its raw audit artifact can reveal the A/B condition, a confidentially blinded pilot is blocked until private evidence storage is available. See SECURITY.md.
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
