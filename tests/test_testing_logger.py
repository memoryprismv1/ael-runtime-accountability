"""Contract tests for the global testing logger, independent of AEL ledger events."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from testing_logger import TestingLogger

class TestingLoggerTests(unittest.TestCase):
    def test_generic_experiment_can_emit_once_or_repeatedly_without_a_b_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            logger = TestingLogger(root / "run", workspace, {"run_id": "response-probe-001"})
            try:
                first = logger.emit("response_started", "experiment", "response", "observed", {"stage": 1})
                second = logger.emit("response_completed", "experiment", "response", "observed", {"stage": 2})
                self.assertEqual(first["seq"], 2)  # seq 1 is the logger's run_started event
                self.assertEqual(second["seq"], 3)
                logger.finish("succeeded")
            finally:
                logger.close()
            events = [json.loads(line) for line in (root / "run" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([event["event_type"] for event in events], ["run_started", "response_started", "response_completed", "run_finished"])
            self.assertEqual(events[2]["prev_event_sha256"], events[1]["event_sha256"])

    def test_independent_experiments_can_use_different_event_vocabularies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for run_id, event_type in [("one", "response"), ("two", "candidate_ranked")]:
                workspace = root / f"workspace-{run_id}"
                workspace.mkdir()
                logger = TestingLogger(root / f"run-{run_id}", workspace, {"run_id": run_id})
                try:
                    logger.emit(event_type, "experiment", "evaluation", "observed", {"run": run_id})
                    logger.finish("succeeded")
                finally:
                    logger.close()
                records = [json.loads(line) for line in (root / f"run-{run_id}" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(records[1]["event_type"], event_type)

if __name__ == "__main__":
    unittest.main()
