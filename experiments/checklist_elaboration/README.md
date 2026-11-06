# Checklist-elaboration planning experiment

This experiment compares Memory Prism (MP) and Critical Thinking (CT) separately and together on a fixed planning task.

## Conditions

- MP off / CT off: ordinary planning baseline
- MP on / CT off: full Memory Prism Starter-Kit
- MP off / CT on: Critical Thinking Basic Skill package
- MP on / CT on: both packages

The tiny optional Memory Prism prompt embedded in the CT package remains part of CT; it is not the full MP factor.

## Safety and autonomy

The agent receives only file inspection, deliverable writing, a simulated `request_input` recorder, and finish tools. The request recorder logs a hypothetical external question and immediately returns no answer. It contacts nobody. There is no live user interaction, browser, network, shell, package install, generated-code execution, or external API tool.

The task and selected skill files are copied into a new workspace as read-only inputs. Only `deliverables/` is writable. Raw request/response logs and the condition key must be stored in a private local directory. Score packets omit raw prompts, skill text, and condition mapping.

## Pinned inputs

The runner verifies both skill checkout commits and the Git blob SHA-1 of each supplied skill file:
- MP: `memoryprismv1/memoryprism` at `5cc48df650b1942412047ee6e82642c14e800967`
- CT: `memoryprismv1/cognitive-interface-ai-skills` at `8152c98d2e388735d8bf63857b46a2056ef0a967`

The task fixture under `task-v1/` is independently pinned by `fixture-manifest.json`.

## Test without a live model

From the repository root:

```bash
python -m unittest experiments.checklist_elaboration.test_runner -v
python -m experiments.checklist_elaboration.runner doctor
```

The unit tests use a fake model client. They do not call Ollama or generate real-model evidence.

## Deliberate real-model feasibility block

Only after tests pass and a private destination is verified:

1. Check out the exact MP and CT commits into separate, clean source directories.
2. Confirm a local Ollama model is installed using `doctor`.
3. Choose a new private raw output directory and a separate private condition-key path.
4. Run:

```bash
python -m experiments.checklist_elaboration.runner run-block \
  --output /private/path/qbatch-checklist-block-01 \
  --key-file /private/path/controller-key-block-01.json \
  --task-dir experiments/checklist_elaboration/task-v1 \
  --mp-source /private/path/memoryprism-checkout \
  --ct-source /private/path/critical-thinking-checkout \
  --model EXACT_INSTALLED_OLLAMA_MODEL_NAME
```

The run output contains raw prompts/responses and workspaces. Do not place it in the public AEL repository, a public Actions artifact, or a shared assessor folder. Keep the controller key separate until all blinded scores are frozen.

One run per condition is only a feasibility block. It is not an efficacy result. Preserve incomplete runs and report coverage, simulated input demand, autonomy, deferrals, quality, and resource costs separately.
