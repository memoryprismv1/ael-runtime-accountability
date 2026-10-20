# Roadmap

This roadmap tracks implementation work, not changes to the author's AEL framework.

## Current main-branch prototype (V2.8.1)

The items below describe the main branch baseline.

## Current prototype

- [x] Append-only local event history and disposable active-context projection.
- [x] Branch exposure primitives and structural pivot/reset.
- [x] Retention separated from current use/influence.
- [x] Controlled local-to-account memory candidate pipeline.
- [x] Bounded model-input allowlist and context packing.
- [x] Delta-first proposal/decision/reset and textual conformance checks.
- [x] Loopback-only Ollama adapter and interactive shell, tested against a mock service.
- [x] Automated tests in GitHub Actions workflow.

## Next engineering steps

1. Run a real local inference test on a machine with Ollama and a suitable local model.
2. Make the runtime load/hash the actual artifact itself at proposal time and re-read it at expansion/verification.
3. Add an independent semantic conformance check for output against an accepted delta; keep textual scope checks separate.
4. Add the memory walk-back decay/reactivation job with explicit, tested defaults.
5. Test restore and migration behavior on real process restarts and back up/restore cycles.
6. Conduct threat-model and data-handling review before recommending use with sensitive content.

## Not planned without evidence

- Paid API requirement for core local persistence mechanics.
- Automatic learning claims or model-weight changes.
- Silent automatic promotion of local lessons into shared account context.
- Automatic locale clustering beyond the author's documented scope.
- A full UI unless a demonstrated use case warrants it.


## V2.9 candidate — Critical-thinking task precommitment

- [x] Pin and vendor a specific critical-thinking skill snapshot with source attribution.
- [x] Add immutable case-note and implementation-plan artifacts with content hashes.
- [x] Bind each user approval to the exact artifact ID and hash.
- [x] Require the implementation plan to reference the approved case hash.
- [x] Block the runtime's execution-start transition until both current artifacts are approved.
- [x] Export the task artifacts, approvals, action records, verification checks, and event chronology in one audit document.
- [ ] Confirm the full suite and new adversarial task-state tests in CI.
- [ ] Integrate a real action executor; this candidate currently records execution steps and outputs but does not operate arbitrary external apps/tools.
- [ ] Add independent semantic verification rather than relying solely on model-authored reports.
