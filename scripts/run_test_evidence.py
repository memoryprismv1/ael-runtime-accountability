#!/usr/bin/env python3
"""Run AEL's standard-library test suite and preserve machine-readable evidence."""
# Q-Batch A/B rehearsal: B intentionally differs from A only by comments.
# No test, collection, evidence, or runtime behavior is changed in this branch.
from __future__ import annotations
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-evidence"
OUT.mkdir(exist_ok=True)
LOG = OUT / "unit-test-run.log"
SUMMARY = OUT / "unit-test-evidence.json"

started = datetime.now(timezone.utc)
cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT, check=False)
ended = datetime.now(timezone.utc)
log_text = proc.stdout
LOG.write_text(log_text, encoding="utf-8")
match = re.search(r"Ran (\d+) tests? in ([0-9.]+)s", log_text)
count = int(match.group(1)) if match else None
duration = float(match.group(2)) if match else None
passed = proc.returncode == 0 and count is not None and "OK" in log_text
log_sha = hashlib.sha256(LOG.read_bytes()).hexdigest()
summary = {
    "schema_version": "qbatch-ael-runtime-evidence/0.1",
    "extends": ["basic-evidence-log/0.1"],
    "batch_id": "ael-unit-tests-" + started.strftime("%Y%m%dT%H%M%SZ"),
    "purpose": "Run the committed AEL Runtime standard-library unit suite and preserve its raw output",
    "specification_ref": "TEST_REPORT.md",
    "condition": "CI unit suite; mock-server integration only; no real model inference",
    "started_at": started.isoformat(),
    "ended_at": ended.isoformat(),
    "executor": {"name": "GitHub Actions ubuntu-latest", "version": platform.python_version()},
    "environment": {
        "os": platform.platform(),
        "reset": "fresh GitHub-hosted job",
        "persistence": "ephemeral runner; uploaded workflow artifact is the preservation mechanism"
    },
    "inputs": [{"ref": "repository checkout", "revision": os.environ.get("GITHUB_SHA")}],
    "resources": [{"path": "tests/", "revision": os.environ.get("GITHUB_SHA")}],
    "procedure": ["python -m unittest discover -s tests -v"],
    "status": "passed" if passed else "failed",
    "events": [
        {"event_id": "test-suite-start", "sequence": 1, "timestamp": started.isoformat(),
         "type": "start", "actor": "GitHub Actions", "action": "run unittest discovery",
         "observation": "test command started", "status": "observed", "evidence_refs": ["unit-test-run.log"]},
        {"event_id": "test-suite-end", "sequence": 2, "timestamp": ended.isoformat(),
         "type": "end" if passed else "error", "actor": "unittest", "action": "finish test suite",
         "observation": {"exit_code": proc.returncode, "tests_reported": count, "duration_seconds": duration},
         "status": "passed" if passed else "failed", "evidence_refs": ["unit-test-run.log"]}
    ],
    "outputs": [{
        "path": "unit-test-run.log",
        "media_type": "text/plain",
        "sha256": log_sha,
        "availability": "preserved"
    }],
    "deviations": [],
    "limitations": [
        "This is a unit-test run, not a real-model inference run.",
        "Mock-server tests establish adapter integration and data-boundary behavior only.",
        "The hosted runner does not preserve artifacts indefinitely; download and archive the workflow artifact if long-term preservation is required."
    ],
    "provenance": {"collector": "scripts/run_test_evidence.py", "collected_at": ended.isoformat()},
    "interpretation": None,
    "ael_runtime": {
        "runtime_version": "V2.8.1 prototype (see repository release/source revision)",
        "runtime_source_sha": os.environ.get("GITHUB_SHA"),
        "ledger_ref": None,
        "ledger_high_watermark": None,
        "audit_sidecar_ref": None,
        "model_input_ref": None,
        "response_ref": None,
        "model_call": {
            "adapter": "mock HTTP server where exercised by tests",
            "model": None,
            "endpoint_class": "loopback mock",
            "inference_mode": "mocked"
        },
        "boundary_checks": [
            {"check": "unit suite exit status", "expected": "zero", "observed": proc.returncode,
             "result": "pass" if passed else "fail"},
            {"check": "test count parsed from unittest summary", "expected": "present",
             "observed": count, "result": "pass" if count is not None else "fail"}
        ],
        "failure_point": None if passed else "unit_test_suite",
        "recovery": {"attempted": False, "prior_attempt_batch_id": None, "notes": None}
    },
    "execution": {
        "command": cmd,
        "exit_code": proc.returncode,
        "tests_reported": count,
        "duration_seconds": duration,
        "log_sha256": log_sha,
        "real_model_inference_performed": False
    }
}
SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Test log: {LOG.relative_to(ROOT)}")
print(f"Evidence record: {SUMMARY.relative_to(ROOT)}")
print(f"Exit code: {proc.returncode}; tests reported: {count}; log sha256: {log_sha}")
sys.stdout.write(log_text)
sys.exit(proc.returncode if match else 2)
