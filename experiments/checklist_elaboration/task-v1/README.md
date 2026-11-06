# Checklist-elaboration task fixture v1

**Classification:** synthetic planning scenario for a controlled Q-Batch experiment.  
**Not:** a real airport deployment, operational policy, or aviation recommendation.

The agent receives `TASK.md` and the read-only `source-pack/` files. The agent does not receive the evaluator's hidden reference set.

## Deliverables

The agent must create three files under `deliverables/`:

1. `plan.md` — an actionable pilot plan, architecture outline, operating flow, delivery sequence, risk controls, and test approach.
2. `consideration-register.json` — additional and fixed considerations, with evidence, scope, disposition, and their effect on the proposed plan.
3. `open-decisions.md` — unresolved project decisions, what can proceed without them, and a safe interim treatment.

The task is deliberately self-contained. **Do not ask the user for more information or wait for a reply.** Inspect the supplied material, resolve what can be resolved, make clearly labelled bounded assumptions where safe, and defer genuinely unavailable decisions while continuing all independent work.

The agent is not asked to implement software, run generated code, browse the web, contact a person, or change any source-pack file. This is a planning and checklist-elaboration test only.

All facts and incident records in this fixture are synthetic.