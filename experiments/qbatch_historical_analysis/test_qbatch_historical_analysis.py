"""Focused tests for the read-only Q-Batch historical analyser."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from qbatch_historical_analysis import (
    analyse_cohorts, canonical_bytes, normalise, policy_for_cohort,
    read_run, sha256_bytes,
)

def record(attempt, signature="same", condition="A", identity_complete=True):
    identity = {"task_brief_sha256": "task", "runner_implementation_revision": "runner-v1"}
    return {
        "attempt_id": attempt, "source_run_url": None, "run_id": attempt + "-" + condition.lower(),
        "condition_label": condition, "format_profile": {"profile": "profile-v1"},
        "integrity": {"status": "PASS"}, "task_identity": identity,
        "task_identity_hash": sha256_bytes(canonical_bytes(identity)),
        "identity_complete": identity_complete,
        "missing_identity_fields": [] if identity_complete else ["runner_implementation_revision"],
        "failure": {"signature": signature},
    }

def write_run(root, *, context=False, event_type="run_finished", evidence=False):
    root.mkdir()
    manifest = {
        "run_id": "fixture-run", "schema_version": "1.0", "logger_version": "0.1.0",
        "condition_label": "A", "task_brief_sha256": "0" * 64,
        "condition_config_sha256": "1" * 64, "started_at_utc": "2026-11-03T00:00:00Z",
        "model": {}, "environment": {}, "resource_limits": {}, "base_commit": "fixture",
    }
    payload = {"logger_version": "0.1.0", "schema_version": "1.0"}
    if context:
        snapshot = {"context_id": "fixture", "version": 1, "purpose": "test"}
        manifest.update(context_id="fixture", context=snapshot)
        payload.update(context_id="fixture", context_sha256=sha256_bytes(canonical_bytes(snapshot)))
    refs = []
    if evidence:
        (root / "artifacts").mkdir()
        data = b"original"
        (root / "artifacts/sample.txt").write_bytes(data)
        refs = [{"path": "artifacts/sample.txt", "sha256": hashlib.sha256(data).hexdigest(),
                 "size_bytes": len(data)}]
    rows, previous = [], None
    for seq, kind in enumerate(("run_started", event_type), 1):
        event = {"schema_version": "1.0", "run_id": "fixture-run", "seq": seq,
                 "timestamp_utc": "2026-11-03T00:00:00Z", "phase": "setup", "actor": "runner",
                 "event_type": kind, "status": "succeeded", "payload": payload if seq == 1 else {},
                 "evidence_refs": refs if seq == 1 else [], "prev_event_sha256": previous}
        event["event_sha256"] = sha256_bytes(canonical_bytes(event))
        previous = event["event_sha256"]
        rows.append(event)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    stream = ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode()
    (root / "events.jsonl").write_bytes(stream)
    (root / "checksums.sha256").write_text(hashlib.sha256(stream).hexdigest() + "  events.jsonl\n")
    return root

class HistoricalAnalysisTests(unittest.TestCase):
    def test_four_comparable_independent_failures_reach_threshold(self):
        rows = []
        for i in range(4):
            rows.extend([record(f"attempt-{i}", condition="A"), record(f"attempt-{i}", condition="B")])
        report = analyse_cohorts(rows)
        self.assertEqual(report["decision"], "eligible_for_batch_diagnosis")
        self.assertEqual(report["cohorts"][0]["independent_attempt_count"], 4)

    def test_two_x_one_y_one_z_is_not_aggregated(self):
        rows = []
        for attempt, signature in (("a1", "X"), ("a2", "X"), ("a3", "Y"), ("a4", "Z")):
            rows.extend([record(attempt, signature, "A"), record(attempt, signature, "B")])
        report = analyse_cohorts(rows)
        self.assertEqual(report["decision"], "INCONCLUSIVE_NO_ELIGIBLE_COHORT_REACHES_MINIMUM")
        self.assertEqual(sorted(x["independent_attempt_count"] for x in report["cohorts"]), [1, 1, 2])

    def test_a_and_b_count_as_one_attempt(self):
        rows = [record("a1", condition="A"), record("a1", condition="B"),
                record("a2", condition="A"), record("a2", condition="B")]
        report = analyse_cohorts(rows)
        self.assertEqual([a["run_count"] for a in report["attempts"]], [2, 2])
        self.assertEqual(report["cohorts"][0]["independent_attempt_count"], 2)

    def test_missing_runner_revision_blocks_four_failure_cohort(self):
        rows = []
        for i in range(4):
            rows.extend([record(f"a{i}", condition="A", identity_complete=False),
                         record(f"a{i}", condition="B", identity_complete=False)])
        report = analyse_cohorts(rows)
        self.assertEqual(report["cohorts"][0]["status"], "ineligible_missing_comparability_metadata")
        self.assertNotEqual(report["decision"], "eligible_for_batch_diagnosis")

    def test_incomplete_or_mixed_pair_is_not_counted(self):
        rows = [record("a1", "X", "A"), record("a1", "Y", "B")]
        report = analyse_cohorts(rows)
        self.assertEqual(report["attempts"][0]["status"], "inconclusive_pair")
        self.assertEqual(report["cohorts"], [])

    def test_rerun_requires_threshold_fix_and_regression(self):
        cohort = {"independent_attempt_count": 4, "threshold": 4}
        self.assertEqual(policy_for_cohort(cohort), "HOLD_NO_VERIFIED_TARGETED_FIX")
        self.assertEqual(policy_for_cohort(cohort, targeted_fix_exists=True), "HOLD_FIX_NOT_VERIFIED")
        self.assertEqual(policy_for_cohort(cohort, targeted_fix_exists=True, regression_test_passed=True),
                         "RECOMMEND_BOUNDED_RERUN_MANUAL_APPROVAL_REQUIRED")

    def test_context_snapshot_is_bound_to_first_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_run(Path(tmp) / "run", context=True)
            self.assertEqual(read_run(root, "attempt")["integrity"]["status"], "PASS")
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["context"]["purpose"] = "tampered"
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "context snapshot"):
                read_run(root, "attempt")

    def test_artifact_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_run(Path(tmp) / "run", evidence=True)
            (root / "artifacts/sample.txt").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "evidence size/hash mismatch"):
                read_run(root, "attempt")

    def test_unknown_event_vocabulary_does_not_qualify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_run(Path(tmp) / "run", event_type="future_event")
            run = read_run(root, "attempt")
            from qbatch_historical_analysis import classify_failure
            self.assertEqual(classify_failure(run)["signature"], "unclassified_unsupported_event_vocabulary")

    def test_unknown_schema_label_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_run(Path(tmp) / "run")
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["schema_version"] = "99.0"
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "unsupported schema/logger labels"):
                read_run(root, "attempt")

if __name__ == "__main__":
    unittest.main(verbosity=2)
