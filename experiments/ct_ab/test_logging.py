from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from .logger import LOGGER_VERSION, SCHEMA_VERSION, RunLogger, utc_now
from .preflight import run_rehearsal
from .validate_log import EVENT_TYPES, STATUSES, LogValidationError, validate_pair, validate_run


class LoggingContractTests(unittest.TestCase):
    def test_full_pair_rehearsal_passes_gate_and_preserves_failure_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "output"
            report = run_rehearsal(root)
            self.assertEqual(report["status"], "PASS")
            for label in ("a", "b"):
                rows = [json.loads(line) for line in (root / f"run-{label}" / "events.jsonl").read_text().splitlines()]
                failed_commands = [e for e in rows if e["event_type"] == "command_finished" and e["status"] == "failed"]
                successful_commands = [e for e in rows if e["event_type"] == "command_finished" and e["status"] == "succeeded"]
                self.assertTrue(failed_commands)
                self.assertTrue(successful_commands)
                self.assertTrue(any(e["event_type"] == "retry" for e in rows))
                self.assertTrue(any(e["event_type"] == "file_changed" and e["payload"].get("path") == "from-command.txt" and e["payload"].get("action") == "created" for e in rows))

    def test_event_tampering_breaks_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "output"
            run_rehearsal(root)
            path = root / "run-a" / "events.jsonl"
            lines = path.read_text().splitlines()
            event = json.loads(lines[1])
            event["payload"]["note"] = "tampered"
            lines[1] = json.dumps(event)
            path.write_text("\n".join(lines) + "\n")
            with self.assertRaises(LogValidationError):
                validate_run(root / "run-a")

    def test_artifact_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "output"
            run_rehearsal(root)
            artifact = next((root / "run-a" / "artifacts").glob("*stdout.txt"))
            artifact.write_text("tampered evidence")
            with self.assertRaises(LogValidationError):
                validate_run(root / "run-a")

    def test_changed_controlled_manifest_field_rejects_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "output"
            run_rehearsal(root)
            manifest_path = root / "run-b" / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["resource_limits"]["timeout_seconds_per_command"] = 999
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(LogValidationError):
                validate_pair(root / "run-a", root / "run-b")

    def test_missing_required_event_fails_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "output"
            run_rehearsal(root)
            with self.assertRaises(LogValidationError):
                validate_pair(root / "run-a", root / "run-b", {"run_started", "impossible_event"})

    def test_logger_refuses_workspace_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            manifest = {"run_id":"x", "condition_label":"A", "task_brief_sha256":"0"*64, "condition_config_sha256":"1"*64, "logger_version":LOGGER_VERSION, "schema_version":SCHEMA_VERSION, "started_at_utc":utc_now(), "model":{}, "environment":{}, "resource_limits":{}, "base_commit":"none"}
            with self.assertRaises(ValueError):
                RunLogger(workspace / "logs", workspace, manifest)

    def test_new_run_never_appends_to_existing_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            out = root / "run"
            manifest = {"run_id":"x", "condition_label":"A", "task_brief_sha256":"0"*64, "condition_config_sha256":"1"*64, "logger_version":LOGGER_VERSION, "schema_version":SCHEMA_VERSION, "started_at_utc":utc_now(), "model":{}, "environment":{}, "resource_limits":{}, "base_commit":"none"}
            logger = RunLogger(out, workspace, manifest)
            logger.finish()
            with self.assertRaises(FileExistsError):
                RunLogger(out, workspace, manifest)

    def test_schema_event_type_enum_matches_validator(self):
        schema_path = Path(__file__).with_name("log_schema.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]["event_type"]["enum"]), EVENT_TYPES)
        self.assertEqual(set(schema["properties"]["status"]["enum"]), STATUSES)
        self.assertEqual(schema["properties"]["schema_version"]["const"], SCHEMA_VERSION)

    def test_model_request_and_response_are_captured_as_distinct_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            manifest = {"run_id":"model-test", "condition_label":"A", "task_brief_sha256":"0"*64, "condition_config_sha256":"1"*64, "logger_version":LOGGER_VERSION, "schema_version":SCHEMA_VERSION, "started_at_utc":utc_now(), "model":{"provider":"mock","model_id":"sample","version":"1"}, "environment":{}, "resource_limits":{}, "base_commit":"none"}
            logger = RunLogger(root / "run", workspace, manifest)
            try:
                logger.record_model_exchange({"provider":"mock", "model_id":"sample", "request_id":"req-1", "latency_ms":12}, "exact prompt", "exact response", {"input_tokens":2, "output_tokens":2})
            finally:
                logger.finish()
            result = validate_run(root / "run")
            self.assertIn("model_request", result["event_types"])
            self.assertIn("model_response", result["event_types"])
            payloads = [json.loads(line) for line in (root / "run" / "events.jsonl").read_text().splitlines()]
            self.assertEqual(sum(e["event_type"] == "model_request" for e in payloads), 1)
            self.assertEqual(sum(e["event_type"] == "model_response" for e in payloads), 1)

    def test_unsafe_artifact_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            manifest = {"run_id":"x", "condition_label":"A", "task_brief_sha256":"0"*64, "condition_config_sha256":"1"*64, "logger_version":LOGGER_VERSION, "schema_version":SCHEMA_VERSION, "started_at_utc":utc_now(), "model":{}, "environment":{}, "resource_limits":{}, "base_commit":"none"}
            logger = RunLogger(root / "run", workspace, manifest)
            try:
                with self.assertRaises(ValueError):
                    logger.capture_artifact("../events.jsonl", "nope")
            finally:
                logger.finish()

if __name__ == "__main__":
    unittest.main()
