from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .multi_task_probe import build_request, run_tasks

SKILL = "# fixture skill\\nNotice contradictions and separate evidence from speculation."
SKILL_OBJ = {
    "critical-thinking": SKILL,
    "approach-calibration-help-seeking": "# AC fixture skill\\nAsk a focused question only when essential.",
}


class FakeClient:
    def __init__(self):
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return {
            "message": {"role": "assistant", "content": "Evidence is limited; the cause is not established."},
            "done_reason": "stop",
            "prompt_eval_count": 100,
            "eval_count": 20,
            "total_duration": 1000
        }


class MultiTaskProbeTests(unittest.TestCase):
    def test_paired_requests_differ_only_in_skill_injection(self):
        prompt = "Report A says 8; table says 10. What follows?"
        off = build_request("test-model", prompt, None)
        on = build_request("test-model", prompt, SKILL_OBJ)
        self.assertEqual(off["messages"][1], on["messages"][1])
        self.assertEqual(off["options"], on["options"])
        self.assertEqual(off["model"], on["model"])
        self.assertNotIn(SKILL, off["messages"][0]["content"])
        self.assertIn(SKILL, on["messages"][0]["content"])
        self.assertIn("Ask a focused question only when essential.", on["messages"][0]["content"])

    def test_all_tasks_capture_both_conditions_and_usage(self):
        tasks = [{
            "id": "conflict-v1",
            "category": "contradiction-detection",
            "prompt": "Report says all on time; table says 8/10 on time.",
            "scoring_criteria": ["Flags the contradiction."]
        }]
        fake = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            report = run_tasks(fake, "test-model", SKILL_OBJ, tasks, Path(tmp))
            self.assertEqual(len(fake.requests), 2)
            pair = report["conditions"]["conflict-v1"]["responses"]
            self.assertFalse(pair["skill_off"]["skill_in_system_message"])
            self.assertTrue(pair["skill_on"]["skill_in_system_message"])
            self.assertEqual(pair["skill_off"]["eval_count"], 20)
            self.assertEqual(len(pair["skill_on"]["skill_hashes"]), 2)
            self.assertTrue(report["request_comparison"]["task_prompts_identical_between_conditions"])
            self.assertTrue(report["request_comparison"]["model_and_options_identical_between_conditions"])
            self.assertTrue(report["request_comparison"]["full_request_payloads_differ_between_conditions"])
            self.assertTrue((Path(tmp) / "multi-task-report.json").is_file())
            for label in ("skill_off", "skill_on"):
                self.assertTrue((Path(tmp) / f"conflict-v1-{label}-request.json").is_file())
                self.assertTrue((Path(tmp) / f"conflict-v1-{label}-response.json").is_file())


if __name__ == "__main__":
    unittest.main()
