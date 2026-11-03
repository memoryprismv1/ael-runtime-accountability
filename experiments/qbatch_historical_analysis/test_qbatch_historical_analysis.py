"""Focused tests for the read-only Q-Batch historical analyser."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from qbatch_historical_analysis import (
    analyse_cohorts, canonical_bytes, normalise, policy_for_cohort,
    read_run, sha256_bytes, classify_failure,
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


    def test_real_failure_signature_text_encoded_tool_calls_not_dispatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            # Sanitized shape observed in run 39592787189: Ollama content is JSON
            # text, not structured tool_calls; the runner dispatches no tool calls.
            content = json.dumps({"name": "submit_plan", "arguments": {"plan": "fixture"}})
            for index in range(4):
                payload = {"created_at": "fixture", "message": {"role": "assistant", "content": content}}
                (artifacts / f"{index:04d}-model-response-fixture.txt").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            events = [
                {"event_type": "error", "payload": {"kind": "model_response_without_tool_call", "turn": n},
                 "evidence_refs": []}
                for n in range(1, 5)
            ]
            run = {"root": root, "events": events, "format_profile": {"unknown_event_types": []}}
            result = classify_failure(run)
            self.assertEqual(result["signature"], "text_encoded_tool_calls_not_dispatched")
            self.assertEqual(result["observed"]["dispatched_tool_calls"], 0)
            self.assertEqual(result["observed"]["json_encoded_tool_responses"], 4)

    def test_real_failure_signature_repeated_no_tool_responses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Sanitized event counts from run 39597455540: 21 no-tool responses,
            # three dispatched calls, then the 24-turn runner limit.
            events = [
                {"event_type": "tool_call", "payload": {"tool_name": name}, "evidence_refs": []}
                for name in ("list_files", "read_file", "read_file")
            ]
            events.extend(
                {"event_type": "error", "payload": {"kind": "model_response_without_tool_call", "turn": n},
                 "evidence_refs": []}
                for n in range(1, 22)
            )
            run = {"root": root, "events": events, "format_profile": {"unknown_event_types": []}}
            result = classify_failure(run)
            self.assertEqual(result["signature"], "repeated_no_tool_responses")
            self.assertEqual(result["observed"]["no_tool_response_events"], 21)
            self.assertEqual(result["observed"]["dispatched_tool_calls"], 3)

    def test_real_failure_signature_first_request_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = [
                {"event_type": "error", "payload": {
                    "kind": "model_request_failed", "turn": 1,
                    "error_type": "TimeoutError", "message": "timed out"
                }, "evidence_refs": []},
                {"event_type": "error", "payload": {
                    "kind": "agent_run_failed", "error_type": "RunnerError",
                    "message": "model request failed on turn 1: timed out"
                }, "evidence_refs": []},
            ]
            run = {"root": root, "events": events, "format_profile": {"unknown_event_types": []}}
            result = classify_failure(run)
            self.assertEqual(result["signature"], "first_request_timeout")
            self.assertEqual(result["observed"]["failed_requests"], 1)
            self.assertTrue(result["observed"]["first_turn_only"])

    def test_real_failure_signature_rejected_plan_resubmission_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            events = []
            # Sanitized shape/count from run 41619488320: 24 dispatched tool
            # calls, including seven rejected repeat submit_plan calls.
            for index in range(24):
                refs = []
                if index in {3, 6, 9, 12, 15, 18, 21}:
                    name = f"{index:04d}-tool-call-output.json"
                    data = {"error": True, "message": "plan may be submitted only once"}
                    (artifacts / name).write_text(json.dumps(data), encoding="utf-8")
                    refs = [{"path": f"artifacts/{name}"}]
                tool_name = "submit_plan" if index in {0, 3, 6, 9, 12, 15, 18, 21} else (
                    "list_files" if index % 3 == 0 else "read_file"
                )
                events.append({
                    "event_type": "tool_call",
                    "payload": {"tool_name": tool_name},
                    "evidence_refs": refs,
                })
            run = {"root": root, "events": events, "format_profile": {"unknown_event_types": []}}
            result = classify_failure(run)
            self.assertEqual(result["signature"], "rejected_plan_resubmission_loop")
            self.assertEqual(result["observed"]["tool_call_count"], 24)
            self.assertEqual(result["observed"]["rejected_plan_submissions"], 7)

if __name__ == "__main__":
    unittest.main(verbosity=2)
