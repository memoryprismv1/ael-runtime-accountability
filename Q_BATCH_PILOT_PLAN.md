# Q-Batch Pilot Plan — AEL Runtime Accountability

**Status:** Prepared; execution pending  
**Method:** Q-Batch of Evidence  
**Purpose:** Replace a context-contaminated, runtime-heavy paired pilot with independently executed evidence batches and offline evaluation.

## What is known

- The repository reports 57 passing unit tests, including CLI and interactive-shell tests against a mocked local Ollama endpoint.
- The repository explicitly states that Ollama was not installed in the development environment and that no real model inference was run there.
- A previous CT pilot attempt was recorded as incomplete after repeated no-tool responses and an audit-event schema mismatch. The audit schema was subsequently corrected for recovery-attempt and loop-detection events.
- Therefore, the current evidence supports local invariants and mock-adapter behaviour, not a claim that the real-model pilot passed.

## Before execution: freeze the contract

Record the exact pilot protocol and version before either batch runs. The protocol must specify:

- the experimental question and what the baseline/CT conditions mean;
- the exact prompts, task cases, allowed resources, instructions and loading sequence for each condition;
- the expected response, runtime logs, audit events, result files and required artefacts;
- the acceptance criteria and scoring rules, including how incomplete runs and missing evidence are treated;
- model name/tag, runtime commit, environment/reset procedure, timeout and retry policy;
- what must remain isolated between runs and what persistence is intentionally retained.

Do not invent missing CT/baseline details. Recover them from the existing evaluation protocol and experiment records before execution.

## Batch A — baseline condition

1. Start from the declared reset state.
2. Record the runtime commit, model tag, environment and loaded resources.
3. Execute only the frozen baseline cases and procedure.
4. Preserve raw prompts/inputs, model responses, runtime audit, logs, result files, errors and timestamps.
5. Mark each case pass, fail, or incomplete against the frozen contract.
6. Freeze the complete evidence set and record its hashes or immutable commit/artifact references where practical.

## Batch B — CT condition

Repeat the same evidence-collection discipline in a separately established environment, loading only the CT condition's declared resources. Do not carry conversational state from Batch A into Batch B. Record intentional differences between conditions. Preserve and freeze the evidence set independently.

Batch A and Batch B may run on different days and need not run consecutively. Do not change the contract between runs without versioning the change.

## Offline comparison

Evaluate the frozen evidence sets against the contract, without rerunning the original test cases merely to reconstruct missing evidence.

Report:

- expected versus observed output for each case and condition;
- audit-schema validity and required event presence;
- response completeness, tool/no-tool behaviour, timeouts and recovery attempts;
- missing, malformed or unexpected artefacts;
- per-condition acceptance scores and the exact scoring basis;
- differences between conditions, confounds, uncertainty and limits on conclusions.

A difference between conditions does not by itself establish its cause. If either batch is incomplete, report that explicitly; do not turn missing evidence into a pass or fail without a predeclared rule.

## Minimum evidence package

Use the Q-Batch templates for one BATCH-RECORD.md per condition and one COMPARISON-RECORD.md. Store raw evidence separately from summaries. Redact secrets and unnecessary personal data without silently editing the preserved raw output; document any redaction.

Suggested layout:

    q-batch/
      contract/
        pilot-protocol.md
      batch-a-baseline/
        BATCH-RECORD.md
        responses/
        logs/
        results/
      batch-b-ct/
        BATCH-RECORD.md
        responses/
        logs/
        results/
      comparison/
        COMPARISON-RECORD.md

## Execution boundary

The GitHub repository connection can inspect and change repository files, but it cannot itself run a local Ollama server on the user's machine. A real-model batch must be executed in an environment where Ollama and the selected local model are installed and available. Until both required evidence sets exist, the pilot remains pending and no real-model outcome should be claimed.
