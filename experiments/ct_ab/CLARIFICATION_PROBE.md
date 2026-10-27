# Selective-clarification probe

## Purpose

This is a small follow-up to the Critical Thinking skill delivery and evidence-interpretation probes. It tests whether adding the pinned skill changes observable responses when the model must distinguish between:

- a task it can answer directly;
- a task blocked by missing information;
- a task with harmless ambiguity where a reasonable default is enough;
- conflicting evidence that should not be silently resolved by choosing one source.

It is deliberately small and exploratory. It is not a benchmark of general intelligence or autonomous help-seeking.

## Controlled setup

The current workflow uses the same model, user prompt, sampling options, and evidence-capture path in both conditions. The only intended treatment difference is whether the exact pinned Critical Thinking skill is included in the system message. Requests and responses are retained as artifacts, alongside token and duration metadata.

The four prompts and task-specific scoring criteria are versioned in `clarification_tasks.json`. A human reviewer should score the observable answer against those criteria rather than judge whether it merely sounds thoughtful.

## What counts as a good result

- **Direct answer:** solve a fully specified, low-risk task without asking an unnecessary question.
- **Necessary clarification:** identify the information that blocks the requested comparison and ask for that information rather than fabricate an answer.
- **Reasonable default:** proceed on a low-consequence ambiguity, using a neutral assumption without inventing specifics.
- **Conflicting evidence:** explicitly identify the mismatch, avoid silently declaring one source authoritative, and request or retrieve the evidence needed to resolve it.

Measure correctness and interaction quality separately from response length, token use, and latency. More questions, more caveats, or a more elaborate answer do not automatically mean better performance.

## Interpretation limits

This first clarification suite is **single-turn text generation**. The model can phrase a question, but it cannot actually pause an agent workflow, obtain a human response, revise its plan, or demonstrate that the answer to the question improves task completion. Therefore it tests clarification *judgement in a response*, not a complete human-in-the-loop capability.

A stronger follow-up should use a small interactive harness with two or more turns and a simulated user/controller that can answer clarification questions. Score at least:

1. whether the agent asks when essential information is missing;
2. whether it avoids asking when it can safely proceed;
3. whether the question targets the information that changes the decision;
4. whether it updates its answer after the reply;
5. whether the final task result improves;
6. the extra turns and token cost.

Keep the user-response policy fixed across conditions, and preserve the complete request/response trace. If a prompt explicitly tells the model it may ask a question, treat the result as conditional performance under that instruction—not proof that the skill independently caused the model to seek help.

## Relevant prior work

- Edwards and Schuster, [Ask or Assume? Uncertainty-Aware Clarification-Seeking in Coding Agents](https://arxiv.org/abs/2603.26233) (2026): evaluates underspecified coding tasks and a scaffold that separates underspecification detection from execution.
- Zhao, Fang, and Cheng, [When and What to Ask: AskBench and Rubric-Guided RLVR for LLM Clarification](https://aclanthology.org/2026.findings-acl.845/) (Findings of ACL 2026): studies intent-deficient queries and false-premise questions in interactive settings.
- Deng et al., [Uncertainty-Aware Clarification in LLM Agents with Information Gain](https://proceedings.mlr.press/v306/deng26l.html) (ICML 2026): rewards questions for how much they reduce uncertainty about the user's goal.
- Kamoi et al., [When Can LLMs Actually Correct Their Own Mistakes?](https://aclanthology.org/2024.tacl-1.78/) (TACL 2024): reviews the limits of prompted self-correction and the role of reliable external feedback.

These papers motivate the test design; their results do not validate this skill or this implementation.
