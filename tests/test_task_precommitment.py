import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "runtime.py"
TASK_PATH = ROOT / "ael_task_precommitment.py"
rspec = importlib.util.spec_from_file_location("runtime_task_tests", RUNTIME_PATH)
runtime = importlib.util.module_from_spec(rspec)
sys.modules[rspec.name] = runtime
rspec.loader.exec_module(runtime)
tspec = importlib.util.spec_from_file_location("task_precommitment_tests", TASK_PATH)
task = importlib.util.module_from_spec(tspec)
sys.modules[tspec.name] = task
tspec.loader.exec_module(task)


class TaskPrecommitmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.con = runtime.connect(self.root / "task.sqlite3")
        task.init(self.con)
        self.account, self.project, self.chat = "acct", "demo", "chat-a"
        task.create(self.con, runtime, "task-1", self.account, self.project, self.chat,
                    "Investigate a question, propose a plan, then do the approved work.", "mock-model")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def submit_approved_case_and_plan(self):
        c = task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat,
                             "## Case\nEvidence and uncertainties recorded.")
        task.decide(self.con, runtime, "task-1", self.account, self.project, self.chat,
                    "case_notes", "approve", "Case supported for planning.")
        p = task.submit_plan(self.con, runtime, "task-1", self.account, self.project, self.chat,
                             "## Plan\n1. Inspect source.\n2. Perform bounded change.\n3. Run tests.")
        return c, p

    def test_dependency_is_pinned_and_bytes_match_git_blob(self):
        body, manifest, content_hash = task.dependency()
        self.assertEqual(manifest["source_commit"], "d1f23e2ad9dafd323940fc6b7a00f1700275d885")
        self.assertEqual(manifest["source_blob_sha"], "d7134969b124e39c04e343bed2ce2475f64b9a64")
        self.assertEqual(len(content_hash), 64)
        self.assertIn("Try to break the preferred explanation", body)

    def test_execution_requires_both_current_approvals(self):
        task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat, "Case notes")
        with self.assertRaisesRegex(ValueError, "requires case notes and implementation plan"):
            task.begin(self.con, runtime, "task-1", self.account, self.project, self.chat)
        task.decide(self.con, runtime, "task-1", self.account, self.project, self.chat, "case_notes", "approve")
        task.submit_plan(self.con, runtime, "task-1", self.account, self.project, self.chat, "Plan")
        with self.assertRaisesRegex(ValueError, "plan is not approved"):
            task.begin(self.con, runtime, "task-1", self.account, self.project, self.chat)
        task.decide(self.con, runtime, "task-1", self.account, self.project, self.chat, "implementation_plan", "approve")
        started = task.begin(self.con, runtime, "task-1", self.account, self.project, self.chat)
        self.assertTrue(started["authorized"])
        self.assertEqual(started["state"], "execution_started")

    def test_plan_cannot_precede_case_approval(self):
        task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat, "Case notes")
        with self.assertRaisesRegex(ValueError, "until the current case is approved"):
            task.submit_plan(self.con, runtime, "task-1", self.account, self.project, self.chat, "Plan")

    def test_changed_case_invalidates_plan_and_old_approval(self):
        self.submit_approved_case_and_plan()
        task.decide(self.con, runtime, "task-1", self.account, self.project, self.chat,
                    "implementation_plan", "approve")
        old = task.snapshot(self.con, "task-1", self.account, self.project, self.chat)
        old_plan_id = old["task"]["current_plan_artifact_id"]
        task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat,
                         "Revised case notes with changed assumptions.")
        new = task.snapshot(self.con, "task-1", self.account, self.project, self.chat)
        self.assertIsNone(new["task"]["current_plan_artifact_id"])
        self.assertNotEqual(old_plan_id, new["task"]["current_plan_artifact_id"])
        with self.assertRaises(ValueError):
            task.begin(self.con, runtime, "task-1", self.account, self.project, self.chat)

    def test_rejected_case_does_not_authorize_plan(self):
        task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat, "Weak case")
        task.decide(self.con, runtime, "task-1", self.account, self.project, self.chat, "case_notes", "reject", "Missing evidence")
        with self.assertRaisesRegex(ValueError, "until the current case is approved"):
            task.submit_plan(self.con, runtime, "task-1", self.account, self.project, self.chat, "Plan")

    def test_artifacts_and_decisions_are_append_only(self):
        c = task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat, "Original case")
        with self.assertRaises(Exception):
            self.con.execute("UPDATE task_artifacts SET content=? WHERE artifact_id=?", ("tampered", c["artifact_id"]))
        with self.assertRaises(Exception):
            self.con.execute("DELETE FROM task_artifacts WHERE artifact_id=?", (c["artifact_id"],))
        task.decide(self.con, runtime, "task-1", self.account, self.project, self.chat, "case_notes", "approve")
        did = self.con.execute("SELECT decision_id FROM task_decisions LIMIT 1").fetchone()[0]
        with self.assertRaises(Exception):
            self.con.execute("DELETE FROM task_decisions WHERE decision_id=?", (did,))

    def test_plan_binds_to_exact_case_hash(self):
        c, p = self.submit_approved_case_and_plan()
        plan = task.current_artifact(self.con, task.get_task(self.con, "task-1", self.account, self.project, self.chat), "implementation_plan")
        case = task.current_artifact(self.con, task.get_task(self.con, "task-1", self.account, self.project, self.chat), "case_notes")
        self.assertEqual(plan["based_on_case_sha256"], case["content_sha256"])
        self.assertEqual(len(plan["content_sha256"]), 64)

    def test_case_submission_event_preserves_previous_state(self):
        c = task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat, "Case notes")
        event = self.con.execute("SELECT from_state,to_state FROM task_events WHERE event_type='task.case_submitted'").fetchone()
        self.assertEqual(tuple(event), ("created", "case_submitted"))

    def test_full_workflow_exports_auditable_record_and_never_overclaims(self):
        self.submit_approved_case_and_plan()
        task.decide(self.con, runtime, "task-1", self.account, self.project, self.chat, "implementation_plan", "approve")
        task.begin(self.con, runtime, "task-1", self.account, self.project, self.chat)
        task.log_action(self.con, runtime, "task-1", self.account, self.project, self.chat,
                        "Read the specified artifact", "completed", "tests/fixture.md", "Content inspected.")
        task.complete(self.con, runtime, "task-1", self.account, self.project, self.chat,
                      "Work completed; one limitation remains.", ["out/result.md"])
        with self.assertRaisesRegex(ValueError, "requires evidence_refs"):
            task.verify(self.con, runtime, "task-1", self.account, self.project, self.chat, "pass",
                        [{"criterion": "Automated test passes", "status": "pass"}])
        report = task.verify(self.con, runtime, "task-1", self.account, self.project, self.chat, "partial",
                             [{"criterion": "Test A", "status": "pass", "evidence_refs": ["out/test-report.txt"]},
                              {"criterion": "Live integration", "status": "not_tested", "notes": "No live endpoint available."}],
                             "Mock checks only.")
        self.assertEqual(report["state"], "verification_recorded")
        snapshot = task.snapshot(self.con, "task-1", self.account, self.project, self.chat)
        output = task.export_markdown(snapshot)
        self.assertIn("Critical-thinking source commit", output)
        self.assertIn("out/test-report.txt", output)
        self.assertIn("not independent proof", output)
        self.assertIn("task.execution_started", output)
        self.assertEqual(snapshot["task"]["state"], "verification_recorded")

    def test_event_ledger_contains_task_lifecycle_events(self):
        task.submit_case(self.con, runtime, "task-1", self.account, self.project, self.chat, "Case notes")
        events = [e["event_type"] for e in runtime.scope_events(self.con, self.account, self.project, self.chat)]
        self.assertIn("task.created", events)
        self.assertIn("task.case_submitted", events)

    def test_cli_exposes_task_workflow(self):
        result = subprocess.run([sys.executable, str(RUNTIME_PATH), "task", "--help"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("generate-case", result.stdout)
        self.assertIn("decide-plan", result.stdout)


if __name__ == "__main__":
    unittest.main()
