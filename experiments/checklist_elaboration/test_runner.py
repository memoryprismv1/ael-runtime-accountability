from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from testing_logger.logger import TestingLogger, LOGGER_VERSION, SCHEMA_VERSION, utc_now
from experiments.ct_ab.validate_log import validate_run
from .runner import (
    ALLOWED, REQUIRED, TOOLS, PlanningAgent, RunnerError, safe_path,
    validate_outputs, prepare_workspace,
)

class FakeClient:
    def __init__(self,calls):
        self.calls=list(calls)
        self.timeout=1
    def chat(self,body):
        if not self.calls:
            raise AssertionError("unexpected model request")
        call=self.calls.pop(0)
        return {
            "message":{"role":"assistant","content":"","tool_calls":[{
                "id":f"fake-{len(self.calls)}",
                "function":{"name":call[0],"arguments":call[1]},
            }]},
            "prompt_eval_count":12,
            "eval_count":3,
            "done_reason":"stop",
        }

def valid_calls(include_request=True):
    calls=[
        ("read_file",{"path":"task/TASK.md"}),
    ]
    if include_request:
        calls.append(("request_input",{
            "question":"Which alert freshness threshold should apply?",
            "why_needed":"No threshold is specified in the task pack.",
            "project_role":"operations owner",
        }))
    calls.extend([
        ("write_file",{"path":"deliverables/plan.md","content":"# Pilot plan\nUse existing feeds and retain source provenance.\n"}),
        ("write_file",{"path":"deliverables/consideration-register.json","content":json.dumps({"items":[]})}),
        ("write_file",{"path":"deliverables/open-decisions.md","content":"The operations owner must approve freshness thresholds before activation. Prototype work can proceed meanwhile.\n"}),
        ("finish",{"summary":"Produced the three planning deliverables.","known_limitations":[]}),
    ])
    return calls

class ChecklistRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.workspace=self.base/"workspace"
        self.workspace.mkdir()
        (self.workspace/"task").mkdir()
        (self.workspace/"source-pack").mkdir()
        (self.workspace/"deliverables").mkdir()
        (self.workspace/"task"/"TASK.md").write_text("fixed task",encoding="utf-8")
        (self.workspace/"source-pack"/"source.md").write_text("fixed evidence",encoding="utf-8")
        self.run_dir=self.base/"logs"/"run-a"
        self.logger=TestingLogger(self.run_dir,self.workspace,{
            "run_id":"unit-run-a",
            "condition_label":"A",
            "task_brief_sha256":"0"*64,
            "condition_config_sha256":"1"*64,
            "logger_version":LOGGER_VERSION,
            "schema_version":SCHEMA_VERSION,
            "started_at_utc":utc_now(),
            "model":{"name":"fake-model"},
            "environment":{"test":True},
            "resource_limits":{"turns":20},
            "base_commit":"test",
        })
    def tearDown(self):
        self.logger.close()
        self.tmp.cleanup()

    def test_tool_allowlist_contains_no_live_human_or_execution_tool(self):
        names={x["function"]["name"] for x in TOOLS}
        self.assertEqual(names,{"list_files","read_file","write_file","request_input","finish"})
        self.assertFalse({"ask_user","send_message","browser","shell","run_command"}&names)

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        with self.assertRaises(ValueError): safe_path(self.workspace,"../outside.txt")
        with self.assertRaises(ValueError): safe_path(self.workspace,str(self.base/"outside.txt"))

    def test_prepare_workspace_copies_task_and_no_skill_when_disabled(self):
        task=self.base/"task-fixture"
        (task/"source-pack").mkdir(parents=True)
        (task/"TASK.md").write_text("task",encoding="utf-8")
        (task/"source-pack"/"incident.json").write_text("{}",encoding="utf-8")
        target=self.base/"prepared"
        info=prepare_workspace(task,target,mp_source=None,ct_source=None,mp_enabled=False,ct_enabled=False)
        self.assertTrue((target/"task"/"TASK.md").is_file())
        self.assertTrue((target/"source-pack"/"incident.json").is_file())
        self.assertTrue((target/"deliverables").is_dir())
        self.assertFalse((target/"skills").exists())
        self.assertIsNone(info["skills"]["memory_prism"])
        self.assertIsNone(info["skills"]["critical_thinking"])
        with self.assertRaises(PermissionError):
            (target/"task"/"TASK.md").write_text("mutation",encoding="utf-8")

    def test_write_tool_refuses_anything_outside_deliverables(self):
        agent=PlanningAgent(self.workspace,self.logger,FakeClient([]),"fake-model")
        with self.assertRaises(ValueError):
            agent.write_file({"path":"task/TASK.md","content":"overwrite"})
        with self.assertRaises(ValueError):
            agent.write_file({"path":"deliverables/../task/TASK.md","content":"overwrite"})
        self.assertEqual((self.workspace/"task"/"TASK.md").read_text(), "fixed task")

    def test_request_input_is_simulated_and_agent_continues(self):
        agent=PlanningAgent(self.workspace,self.logger,FakeClient(valid_calls()),"fake-model")
        metrics=agent.run()
        self.assertEqual(metrics["status"],"succeeded")
        self.assertEqual(metrics["simulated_input_requests"],1)
        self.assertTrue((self.workspace/"deliverables"/"plan.md").is_file())
        self.assertFalse(any("notification" in p.name for p in self.base.rglob("*")))

    def test_repeated_identical_request_stops_without_waiting(self):
        calls=[
            ("request_input",{"question":"Which policy?","why_needed":"Missing","project_role":"ops"}),
            ("request_input",{"question":"Which policy?","why_needed":"Missing","project_role":"ops"}),
        ]
        agent=PlanningAgent(self.workspace,self.logger,FakeClient(calls),"fake-model")
        result=agent.run()
        self.assertEqual(result["status"],"failed")
        self.assertIn("repeated identical",result["stop_reason"])
        self.assertEqual(agent.tool_count,2)
        self.assertEqual(len(agent.input_requests),1)

    def test_no_tool_repetition_is_bounded(self):
        class NoToolClient:
            timeout=1
            def chat(self,body):
                return {"message":{"role":"assistant","content":"I will continue thinking."},"prompt_eval_count":3,"eval_count":2}
        agent=PlanningAgent(self.workspace,self.logger,NoToolClient(),"fake-model")
        result=agent.run()
        self.assertEqual(result["status"],"failed")
        self.assertIn("no-tool",result["stop_reason"])
        self.assertEqual(result["turns"],2)

    def test_deliverable_validator_checks_register_schema(self):
        out=self.workspace/"deliverables"
        (out/"plan.md").write_text("plan",encoding="utf-8")
        (out/"open-decisions.md").write_text("no open decisions",encoding="utf-8")
        (out/"consideration-register.json").write_text(json.dumps({"items":[{"id":"X"}]}),encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_outputs(self.workspace)

    def test_valid_outputs_pass(self):
        out=self.workspace/"deliverables"
        (out/"plan.md").write_text("plan",encoding="utf-8")
        (out/"open-decisions.md").write_text("no open decisions",encoding="utf-8")
        item={
            "id":"C-1","statement":"Preserve receive time","category":"data",
            "source_type":"derived consideration","evidence":["source-pack/source.md"],
            "why_it_matters":"Late messages can arrive out of sequence",
            "disposition":"derived and addressed","action":"Store both timestamps",
            "plan_effect":"Data model and tests",
        }
        (out/"consideration-register.json").write_text(json.dumps({"items":[item]}),encoding="utf-8")
        report=validate_outputs(self.workspace)
        self.assertEqual(report["status"],"PASS")
        self.assertEqual(report["consideration_count"],1)

    def test_run_log_validates_for_four_condition_label(self):
        for name in REQUIRED:
            p=self.workspace/"deliverables"/name
            p.write_text("not empty",encoding="utf-8")
        (self.workspace/"deliverables"/"consideration-register.json").write_text('{"items":[]}',encoding="utf-8")
        self.logger.emit("preflight_check","runner","verification","succeeded",{"check":"test"})
        self.logger.finish("succeeded","unit test")
        self.logger.close()
        report=validate_run(self.run_dir)
        self.assertEqual(report["condition_label"],"A")
        self.assertGreater(report["events"],1)

if __name__=="__main__":
    unittest.main()
