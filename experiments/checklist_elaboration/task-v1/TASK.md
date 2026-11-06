# Task: plan a baggage-transfer exception coordination pilot

## Situation

A medium-sized airport transfer hub handles checked baggage across multiple airlines and ground-handling companies. The existing baggage-reconciliation system, departure-control systems, and sorting/conveyor systems will remain in place.

The airport has approved a small operational coordination layer for staff. Its purpose is to help staff identify checked bags that may miss their onward connection and decide whether a human intervention is useful.

The first pilot is limited to one terminal and a small group of participating airlines/handlers. Produce a practical plan for that pilot, not a complete airport-wide architecture.

## Fixed requirements

1. Give operations staff a shared view of a bag's latest known location, the source and freshness of that information, the intended onward flight, and the reason it may be at risk.
2. Ingest or reference relevant information from existing systems. Do not replace those systems.
3. Handle events that arrive late, more than once, out of order, or not at all.
4. Let authorised staff acknowledge an alert, assign or record an intervention, and record its outcome.
5. Preserve a traceable record of alerts and staff actions.
6. Make uncertainty visible. A missing scan must not automatically be treated as proof that a bag is lost or has not moved.
7. The software may inform and support staff. It must not autonomously hold or delay an aircraft, command a conveyor/sorter, or make an operational decision reserved to people.

## Non-goals

- Replacing baggage-reconciliation, departure-control, or baggage-handling systems.
- Controlling aircraft, sorters, conveyors, or physical baggage routing.
- A passenger-facing baggage-tracking application.
- An autonomous decision system.
- A machine-learning model as a prerequisite for the first pilot.

## Known unknowns

The supplied materials intentionally do not settle every detail. Examples include which system is authoritative for each data field, acceptable alert latency, event-retention periods, exact role permissions, and operational risk thresholds.

Do not invent these as established facts. Decide what can be designed safely now, record explicit assumptions, and list decisions that a future project owner or operations role must settle before the affected feature is activated. Do not stop the whole plan because one decision is open.

## Working instructions

- Use only the task and local source-pack files. They are the complete evidence environment for this exercise.
- There is **no live user or sponsor available** during a run. Do not send a real message, ask the experiment user for homework, or wait for a human response.
- The runner provides a simulated `request_input` tool. Use it only after checking the supplied materials, when you genuinely want to record a question that would otherwise be put to a project sponsor or authorised role. It records the question for measurement, immediately returns that no answer is available, and contacts nobody. It is not a route to receive information. Do not retry it or wait.
- A simulated input request is not a substitute for the required `open-decisions.md` entry. Record the open decision, responsible project role, safe interim treatment, work that can continue, and activation gate.
- Resolve what can be resolved from the supplied material, make clearly labelled bounded assumptions where safe, and defer genuinely unavailable decisions while continuing all independent work.
- Do not add external scope merely to make the plan look comprehensive.
- Distinguish facts in the supplied material from inference and assumption.
- Keep the plan concise enough to act on. More checklist items are not automatically better.
- Create the three required deliverables under `deliverables/`.
- Finish with a factual summary of the files produced and any important limitations.