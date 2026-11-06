# Q-Batch instrumentation preflight — 5 November 2026

**Source artifact:** `ct-ab-instrumentation-preflight`, artifact ID `13398637240`, from [routine CI #388](https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/41991737810).  
**Archive SHA-256:** `856b8f02ccf14be1abeac1b6a324b77a90a5ad919ebb783279244970475e038e`.

The synthetic preflight completed with **PASS**. It created two rehearsal runs, A and B, with 31 events each. Both event streams, manifests, hash chains and controlled manifest fields validated. The runs captured failed commands, errors, retries, successful recovery commands, file changes, model/tool request structures, and test results.

- Evidence references verified: 26 in run A + 26 in run B = **52**.
- The two runs used the same pinned runner implementation revision and capture-profile hash.
- Run output and agent workspaces were separate.
- Eight preflight checks passed.
- No actual model response or quality score was used. The rehearsal is instrumentation verification only, not a Critical Thinking result.
