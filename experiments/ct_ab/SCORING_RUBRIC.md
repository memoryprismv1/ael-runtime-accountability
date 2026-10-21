# Blind A/B scoring rubric — CT skill software task (v1.0)

## Scoring procedure

Score each packet independently. Packets should be labelled only A or B. Do not open the separate controller-private condition key, inspect raw model request/response artifacts, or discuss scores with other assessors until your scorecard is submitted. Do not infer which condition used the skill from style or implementation quality.

Treat the fixed acceptance report as an objective, reproducible product check; do not override it with an overall impression. The human rubric captures quality beyond the specific acceptance tests and should cite concrete evidence.

This evaluates one small software task. It does not directly observe hidden cognition and does not establish general reasoning ability from one run.

## Rating scale (apply to every dimension)

- **1 — Poor:** substantial requirement misses, broken behavior, or no credible evidence for the dimension.
- **2 — Weak:** major defects or omissions; only partial evidence of the required quality.
- **3 — Adequate:** broadly usable and understandable; some weaknesses remain.
- **4 — Strong:** good quality with only minor weaknesses; clear supporting evidence.
- **5 — Excellent:** unusually complete and robust for this task; convincing evidence across relevant cases.

Do not score hidden reasoning. Score only the submitted plan, observable development trace, delivered source, tests, documentation and independently observed behavior.

## Dimensions

1. **Requirements fidelity** — Does the application implement the client brief and contract, including persistence, validation, card lifecycle and the agreed API?
2. **Functional robustness** — How well does it handle invalid input, missing records, restarts, edge cases and failure without corrupting state or crashing?
3. **Interface usability and completeness** — Is the board understandable and usable? Are add, edit, move and delete controls actually wired to server state, and are errors visible?
4. **Maintainability and simplicity** — Is the implementation coherent, appropriately small, readable, and free of unnecessary dependencies or brittle shortcuts?
5. **Testing and documentation** — Are local tests meaningful, were checks actually run, does README explain use and persistence, and are limitations stated accurately?
6. **Process discipline from observable evidence** — Does the submitted plan relate to the client brief? Does the logged activity show inspection, verification, useful recovery from observed failures, and a factual final report? Do not reward a polished narrative unsupported by command/test/file evidence.

## Evidence and disagreement

For every dimension, give a brief rationale and at least one concrete evidence pointer where possible: source path/function, acceptance check name, or event sequence. Distinguish missing evidence from poor quality. Use the preference value unable_to_judge only when the pair cannot fairly be compared; document why.

After both packets have been scored separately, record overall preference as A, B, tie, or unable to judge, plus confidence from 1 to 5. Do not silently reconcile independent scores. Preserve each assessor's original scorecard and report disagreements before any adjudication.

## Interpretation

A difference in one paired run is exploratory and task-specific. If one implementation passes more acceptance checks, report that fact separately. Do not conclude that the skill generally improves reasoning without repeated controlled pairs, independent assessors, preserved disagreement, and analysis of resources and failure patterns.
