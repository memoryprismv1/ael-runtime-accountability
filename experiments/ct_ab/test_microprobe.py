from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .microprobe import PROMPT, build_probe_request, run_probe
from .agent_loop import BASE_SYSTEM, build_system_prompt
from .microprobe import PROBE_SYSTEM


SKILL = "# Tiny fixture skill\nNotice conflicting evidence and state what remains unknown."


class FakeClient:
    def __init__(self):
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return {"message": {"role": "assistant", "content": "The ratio changed; cause remains unknown."}, "done_reason": "stop"}


class MicroprobeTests(unittest.TestCase):
    def test_production_prompt_builder_includes_exact_skill_only_when_enabled(self):
        off = build_system_prompt(None, PROBE_SYSTEM)
        on = build_system_prompt(SKILL, PROBE_SYSTEM)
        self.assertEqual(off, PROBE_SYSTEM)
        self.assertNotIn("Kanban", off)
        self.assertNotIn(SKILL, off)
        self.assertIn(SKILL, on)
        self.assertIn("=== CRITICAL THINKING SKILL (verbatim supplied file) ===", on)
        self.assertTrue(on.endswith("=== END CRITICAL THINKING SKILL ===\n"))

    def test_probe_requests_keep_task_identical_and_only_change_skill_condition(self):
        off = build_probe_request("test-model", None)
        on = build_probe_request("test-model", SKILL)
        self.assertEqual(off["messages"][1], on["messages"][1])
        self.assertIn("Separate what the figures imply", off["messages"][0]["content"])
        self.assertNotIn("Kanban", off["messages"][0]["content"])
        self.assertEqual(off["messages"][1]["content"], PROMPT)
        self.assertEqual(off["options"], on["options"])
        self.assertEqual(off["model"], on["model"])
        self.assertNotEqual(off["messages"][0]["content"], on["messages"][0]["content"])
        self.assertNotIn(SKILL, off["messages"][0]["content"])
        self.assertIn(SKILL, on["messages"][0]["content"])

    def test_transport_boundary_captures_both_requests_and_responses(self):
        fake = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = run_probe(fake, "test-model", SKILL, root)
            self.assertEqual(len(fake.requests), 2)
            self.assertFalse(report["conditions"]["skill_off"]["skill_in_system_message"])
            self.assertTrue(report["conditions"]["skill_on"]["skill_in_system_message"])
            self.assertEqual(report["conditions"]["skill_on"]["skill_sha256"], hashlib.sha256(SKILL.encode()).hexdigest())
            for label in ("skill_off", "skill_on"):
                req = json.loads((root / f"{label}-request.json").read_text())
                resp = json.loads((root / f"{label}-response.json").read_text())
                self.assertEqual(req["messages"][1]["content"], PROMPT)
                self.assertEqual(resp["message"]["content"], "The ratio changed; cause remains unknown.")
            self.assertTrue((root / "probe-report.json").is_file())


if __name__ == "__main__":
    unittest.main()
