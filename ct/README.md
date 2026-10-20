# AEL CT Experiment — Task Precommitment

Isolated experimental environment, not a release. The repository-root implementation remains the control. This tree contains a copy of the runtime, chat launcher, tests and task-precommitment module to test a pinned critical-thinking skill without merging CT changes into baseline.

Run from the root:
- python run_ael.py --path ct runtime task --help
- python run_ael.py --path ct chat
- python compare_environments.py

AEL_PATH is inherited by child processes. CT entry points require it to match this directory; the startup launcher validates experiment.json and skill integrity. A case must be approved before its plan, the plan is bound to the case hash, and execution is blocked until both current artifacts are approved. Replacing the case invalidates the plan. Audit and verification records are append-only.

Case/plan generation can use the local Ollama adapter. This is not a general external-app executor and does not connect directly to ChatGPT/Claude websites. Passing software tests does not establish the skill's reasoning reliability.
See ../EXPERIMENT_ENVIRONMENTS.md for path, dependency and comparison details.
