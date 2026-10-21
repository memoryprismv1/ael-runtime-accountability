# Critical Thinking (CT) Skill Evaluation Plan

**Status:** Pilot design only. No model-quality result has yet been produced.

## Objective

Test whether making the pinned Critical Thinking skill available improves observable investigation quality on fixed tasks. This is separate from AEL's software regression suite: passing unit tests shows that tested software checks passed; it does not establish that CT improves reasoning.

The initial benchmark is a small **closed-world pilot** with self-contained evidence and case-specific scoring anchors. It does not establish general research ability or transfer to open-world investigation.

## Conditions

Run every case under the same three conditions where feasible:

1. **Baseline:** same task, without the CT skill.
2. **CT:** same task, with the exact skill revision pinned in the CT environment genuinely available to the model.
3. **Optional neutral control:** same task with neutral presentation instructions of roughly comparable length, but no substantive critical-thinking guidance. Record the exact wording.

Keep model/provider, model version, task text, evidence, tools and settings as consistent as possible. Record unavoidable differences. Use fresh isolated sessions; do not leak an earlier condition's response into another. Randomize condition order when practical and record the order/seed. Do not label a run CT-enabled unless the skill really was loaded into the context that produced the response. Record the CT skill commit and blob SHA from ct/experiment.json.

## Fixed benchmark

The canonical set is ct-evaluation/benchmark-v1.json, benchmark ID ct-closed-world-pilot-v1, version 1.0.0. It covers numerical reconciliation, overlapping categories, stale-source/provenance mismatch, competing hypotheses, falsification of a preferred attribution, belief revision, clock normalization, confounding, a simple-task control, and separating observation from explanation.

Do not silently change the benchmark between conditions. A substantive change gets a new version; do not pool different versions as if the cases were identical.

## Scoring

Score the visible answer, not hidden chain-of-thought and not the model's self-assessment. Score every applicable dimension from 0 to 4 using the rubric in the benchmark:

- **Accuracy:** correctness of the central answer.
- **Evidence:** faithful use of supplied facts; claims are traceable to the evidence.
- **Contradictions / alternatives:** notices mismatches, ambiguity, competing explanations, and possible discriminating tests where relevant.
- **Calibration:** distinguishes fact, inference, and unknown; confidence matches evidence.
- **Scope discipline:** proportionality, responsiveness to the actual request, and avoidance of unsupported assumptions.

The benchmark's applicable_dimensions field defines which dimensions count for each case. Use null for a genuinely non-applicable dimension, not zero. Do not reward eloquence, length, or confidence by themselves. Use the same case-specific must_notice and score_4_anchors for every condition.

Where practical, replace condition labels with random response IDs before scoring. Keep raw responses and evidence-based notes in the scorecard. Resolve rubric ambiguities before unblinding condition labels where feasible.

### Independent assessor records

New scorecards use schema `1.1`. Each response stores its raw answer once and contains an `assessments` array. Each assessment has a unique `assessor_id`, an independent `scores` object and `rationale_notes`. Do not average or reconcile ratings before recording them. Use stable pseudonymous assessor IDs if names should not appear in the scorecard; keep their mapping separately where needed. Assessor identity should not reveal which model condition produced a response before blinded scoring is complete.

The report includes pooled descriptive scores plus per-case/per-dimension rating ranges, the number of multi-rater cases, and the number where ratings differ. These summaries make disagreement visible; they do not decide which assessor is correct. Preserve each assessment's individual scores and notes in the scorecard. Existing schema `1.0` scorecards with response-level `assessor`, `scores`, and `rationale_notes` remain readable and are treated as one-assessor records.

## First-run procedure

1. Freeze the branch commit, benchmark file, model/provider/version, tools/settings, CT skill commit/blob, and neutral-control wording if used.
2. Initialize one scorecard. Record how condition order and fresh-session isolation were handled.
3. Capture raw responses verbatim. Do not polish or summarize them before scoring.
4. Score each response against the fixed anchors; add brief evidence-based notes for non-obvious ratings.
5. Validate the scorecard and generate a machine-readable report.
6. Inspect case-level outcomes and failures as well as aggregates. A ten-case pilot is useful for finding failure modes, not for claiming universal capability.

## Required reporting

Report response/score completeness; per-condition means by dimension and case; denominators; paired CT-minus-baseline deltas; optional CT-minus-neutral deltas; case-level wins, ties and losses; simple-task control performance; assessor counts and disagreement ranges; missing data; deviations; and technical failures. Do not make broad claims from one average or cherry-picked success. With only ten tasks, emphasize individual cases and uncertainty rather than significance claims.

A later **open-world** stage should separately test source discovery, provenance, conflicting external evidence, and evidence-backed synthesis with tools held constant and source snapshots archived. Keep that separate because live sources and retrieval results change.

## Interpretation boundary

- A passing CI run establishes only that the reported software tests passed.
- A completed pilot gives comparative observations for this model, setup, skill version, rubric, and task set.
- It does not prove general CT efficacy, permanent model learning, or transfer to another model/platform.
- This plan contains no claim that model inference or answer-quality testing has already occurred.

## Tooling

ct-evaluation.py creates a blank scorecard, validates independent ratings and completeness, and calculates descriptive summaries, paired deltas, and assessor-disagreement summaries. It does not call a model or automatically judge answer quality.

Initialize:
python ct-evaluation.py init --output ct-evaluation/run.json --model MODEL_NAME --model-version VERSION

Include the optional neutral control:
python ct-evaluation.py init --output ct-evaluation/run.json --model MODEL_NAME --model-version VERSION --include-neutral

Validate:
python ct-evaluation.py validate ct-evaluation/run.json --require-complete

Report:
python ct-evaluation.py report ct-evaluation/run.json --out ct-evaluation/report.json

Run the deterministic software comparison separately:
python compare_environments.py --out comparison-report.json