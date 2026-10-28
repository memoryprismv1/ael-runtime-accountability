## Basic Q-Batch evidence review

Q-Batch includes an optional, small offline evidence checker. It produces a readable Markdown report without requiring the Peer Review skill:

```bash
python scripts/qbatch_basic_review.py --record test-evidence/unit-test-evidence.json --log test-evidence/unit-test-run.log --report test-evidence/basic-review.md
```

The checker verifies that the raw log exists, its SHA-256 matches the structured record, the record reports a successful process exit/status, and a test summary is present. It flags missing traceability fields and explicitly labels mocked/unit-only evidence. A blocking finding returns exit code 1.

This is deliberately basic: it does **not** validate every Q-Batch schema/event requirement, verify all referenced artifacts, compare blind A/B manifests, run an independent acceptance suite, assess output quality, or establish skill effectiveness. A clean report is not a valid-pair certificate. The experiment-specific acceptance gate remains authoritative.

For users who want cumulative review across batches, mixed-topic collation, disagreement tracking, minority findings, and broader qualitative review, the [Peer Review skill](https://github.com/memoryprismv1/cognitive-interface-ai-skills/tree/main/peer-review) is available as an optional extension. Q-Batch's basic workflow does not depend on it.
