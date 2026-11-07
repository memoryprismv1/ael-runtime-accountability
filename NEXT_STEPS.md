# AEL Runtime — Next Steps / Handoff

**Current main:** `301fb4bec68829460509851d83d2e225a859faad`  
**Current phase:** Close the remaining action-authority gap and decide the real host/context scope.  
**Latest CI:** PR [#32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32), run [#445](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42377856668), passed 85 tests on Python 3.11, 3.12 and 3.13.

## Merged and recorded

- [PR #30](https://github.com/memoryprismv1/ael-runtime-accountability/pull/30) — multi-user participant registry and actor attribution. Merge commit: `1eb82061768f2b9a84a1e6f066bc3d64c3792406`.
- [PR #31](https://github.com/memoryprismv1/ael-runtime-accountability/pull/31) — CSV roster importer and 16-step multi-user workflow fixture. Merge commit: `292fc42bcd7e0f4c930391fe69da17e910072c67`. CI [#442](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42375531422): 82 tests on all three Python versions.
- [PR #32](https://github.com/memoryprismv1/ael-runtime-accountability/pull/32) — active membership enforcement at canonical event append, branch-proposal pre-write check, and chat-scoped external context intervention. Merge commit: `301fb4bec68829460509851d83d2e225a859faad`. CI [#445](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/42377856668): 85 tests on all three Python versions.

See [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) for the chronology, reasons, code changes, verification and retained limits.

## Next work

1. **Close enforcement gaps:** audit direct supporting-table writes, especially memory lifecycle actions and checkpoint creation. Make sure a named human/AI actor cannot use those paths while outside the relevant participation period.
2. **Separate membership from authority:** define a capability/delegation rule and test an active participant who lacks approval authority. Do not grant permission merely because someone is present or has a role label.
3. **Clarify context scope:** decide whether project-level instructions/files should affect multiple chats and how their versions are correlated. Current interventions are account/project/chat scoped only.
4. **Host adapter:** use a real authenticated participant roster and join/leave feed when available. No replacement multi-user UI is needed unless the host demands it.
5. **External behavior evidence:** correlate AEL context events with the exact prompt/context hash delivered to a real model. Current fixture tests are not proof of live ChatGPT behaviour or real-model quality.

## Boundaries

- AEL owns runtime activity and context-intervention records.
- Q-Batch owns experiment execution and cross-run evidence.
- The Differential has not been modified; reference-only use remains the default unless a separate write is justified and approved.

## Guardrails

- This is not the complete AEL runtime.
- Membership does not prove reading, comprehension, notice, or approval permission.
- The context fixture models an AEL-side intervention; it does not reproduce hosted ChatGPT shared-project behaviour.
- No real local-model inference is claimed without a captured run.
- Retain participant periods and superseded context versions as history.
