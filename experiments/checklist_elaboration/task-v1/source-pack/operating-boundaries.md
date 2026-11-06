# Synthetic source-pack: operating boundaries and open policies

**Fixture data only.** These are fixed constraints for this planning exercise.

## Authority boundary

- Operations staff remain responsible for deciding whether to intervene.
- The coordination layer may surface a risk, show supporting events, recommend that staff investigate, and record an action.
- The coordination layer must not hold or delay an aircraft, command physical baggage equipment, or claim that it has physically moved a bag.
- An alert is not proof that a bag is lost or that an intervention succeeded.

## What is not specified

The following policies have not been supplied:

- which role may acknowledge, assign, or close an alert;
- whether all airline/handler partners can see all bags or only their own;
- the acceptable age of a location/event before it is labelled stale;
- how many minutes before departure should trigger a priority level;
- how long detailed event and action history must be retained;
- the fallback process during a source-system outage;
- which source wins when two sources disagree about a field.

These are project decisions, not facts the agent may invent. A good plan should identify them, explain why they matter, and show what can be built before they are settled. For example, a prototype can display timestamps and uncertainty without claiming a validated freshness threshold.

## Pilot boundary

Keep the first pilot to one terminal and a small set of participating airlines/handlers. Do not design a full airport transformation. Use the existing event and flight feeds as inputs, preserve source references, and keep the staff workflow observable and auditable.