from __future__ import annotations
import json
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .agent_loop import AgentLoop, OllamaClient, RunnerError, _parse_text_encoded_tool_call
from .acceptance import run_acceptance
from .logger import LOGGER_VERSION, SCHEMA_VERSION, RunLogger, utc_now
from .paired_runner import run_pair

MOCK_APP_SOURCE = "import argparse\nimport json\nimport os\nimport re\nimport uuid\nfrom http.server import BaseHTTPRequestHandler, HTTPServer\nfrom pathlib import Path\nfrom urllib.parse import urlparse\n\nCOLUMNS = [{\"id\":\"todo\",\"title\":\"To Do\"},{\"id\":\"in_progress\",\"title\":\"In Progress\"},{\"id\":\"done\",\"title\":\"Done\"}]\nDATA_FILE = Path(os.environ.get(\"BOARD_DATA_FILE\", \"board-state.json\"))\nHTML = \"\"\"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Task Board</title></head><body>\n<header><h1>Task Board</h1></header><main id=\"board\"></main>\n<form id=\"create-card-form\"><input id=\"card-title\" name=\"title\" required><textarea id=\"card-description\" name=\"description\"></textarea>\n<select id=\"card-column\" name=\"column_id\"><option value=\"todo\">To Do</option><option value=\"in_progress\">In Progress</option><option value=\"done\">Done</option></select>\n<button type=\"submit\" data-action=\"create\">Create card</button><p id=\"error-message\" role=\"alert\"></p></form>\n<template id=\"card-template\"><article class=\"card\"><h3></h3><p></p><button data-action=\"edit\">Edit</button><button data-action=\"move\">Move</button><button data-action=\"delete\">Delete</button></article></template>\n<script>\nasync function refreshBoard(){const response=await fetch('/api/board');const data=await response.json();document.querySelector('#board').replaceChildren();for(const column of data.columns){const section=document.createElement('section');section.dataset.column=column.id;const heading=document.createElement('h2');heading.textContent=column.title;section.append(heading);for(const card of column.cards){const node=document.querySelector('#card-template').content.cloneNode(true);node.querySelector('.card').dataset.cardId=card.id;node.querySelector('h3').textContent=card.title;node.querySelector('p').textContent=card.description;section.append(node);}document.querySelector('#board').append(section);}}\ndocument.querySelector('#create-card-form').addEventListener('submit',async e=>{e.preventDefault();const title=document.querySelector('#card-title').value;const description=document.querySelector('#card-description').value;const column_id=document.querySelector('#card-column').value;const response=await fetch('/api/cards',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,description,column_id})});if(!response.ok){document.querySelector('#error-message').textContent='Please check the card details.';return;}await refreshBoard();});\ndocument.querySelector('#board').addEventListener('click',async event=>{const button=event.target.closest('button[data-action]');if(!button)return;const card=button.closest('[data-card-id]');if(!card)return;const id=card.dataset.cardId;if(button.dataset.action==='delete'){await fetch('/api/cards/'+id,{method:'DELETE'});await refreshBoard();return;}if(button.dataset.action==='edit'){const title=prompt('Edit title',card.querySelector('h3').textContent);if(title===null)return;const description=prompt('Edit description',card.querySelector('p').textContent);if(description===null)return;await fetch('/api/cards/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,description})});await refreshBoard();return;}if(button.dataset.action==='move'){const columns=['todo','in_progress','done'];const index=columns.indexOf(card.parentElement.dataset.column);const column_id=columns[(index+1)%columns.length];await fetch('/api/cards/'+id+'/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({column_id})});await refreshBoard();}});\nrefreshBoard();\n</script></body></html>\"\"\"\n\ndef load_state():\n    if not DATA_FILE.exists():\n        return {\"cards\":[]}\n    try:\n        data=json.loads(DATA_FILE.read_text(encoding=\"utf-8\"))\n        if isinstance(data,dict) and isinstance(data.get(\"cards\"),list):\n            return {\"cards\":data[\"cards\"]}\n    except (OSError,ValueError):\n        pass\n    return {\"cards\":[]}\n\ndef save_state(state):\n    DATA_FILE.parent.mkdir(parents=True,exist_ok=True)\n    temporary=DATA_FILE.with_suffix(DATA_FILE.suffix+\".tmp\")\n    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2)+\"\\n\",encoding=\"utf-8\")\n    temporary.replace(DATA_FILE)\n\ndef valid_column(value):\n    return any(column[\"id\"]==value for column in COLUMNS)\n\nclass Handler(BaseHTTPRequestHandler):\n    def _send(self,status,body=b\"\",content_type=\"application/json; charset=utf-8\"):\n        self.send_response(status)\n        self.send_header(\"Content-Type\",content_type)\n        self.send_header(\"Content-Length\",str(len(body)))\n        self.end_headers()\n        if body:\n            self.wfile.write(body)\n    def _json(self,status,doc):\n        self._send(status,json.dumps(doc,ensure_ascii=False).encode(\"utf-8\"))\n    def _body(self):\n        length=int(self.headers.get(\"Content-Length\",\"0\"))\n        if length>100_000:\n            raise ValueError(\"request too large\")\n        raw=self.rfile.read(length) if length else b\"{}\"\n        doc=json.loads(raw.decode(\"utf-8\"))\n        if not isinstance(doc,dict):\n            raise ValueError(\"JSON body must be an object\")\n        return doc\n    def do_GET(self):\n        path=urlparse(self.path).path\n        if path==\"/\":\n            return self._send(200,HTML.encode(\"utf-8\"),\"text/html; charset=utf-8\")\n        if path==\"/api/board\":\n            state=load_state()\n            columns=[]\n            for spec in COLUMNS:\n                columns.append({**spec,\"cards\":[card for card in state[\"cards\"] if card.get(\"column_id\")==spec[\"id\"]]})\n            return self._json(200,{\"columns\":columns})\n        return self._json(404,{\"error\":\"not found\"})\n    def do_POST(self):\n        path=urlparse(self.path).path\n        try:\n            body=self._body()\n        except (ValueError,UnicodeDecodeError) as exc:\n            return self._json(400,{\"error\":str(exc)})\n        if path==\"/api/cards\":\n            title=body.get(\"title\")\n            description=body.get(\"description\",\"\")\n            column_id=body.get(\"column_id\",\"todo\")\n            if not isinstance(title,str) or not title.strip() or len(title.strip())>160:\n                return self._json(400,{\"error\":\"title must contain 1 to 160 characters\"})\n            if not isinstance(description,str) or len(description)>1000:\n                return self._json(400,{\"error\":\"description must be at most 1000 characters\"})\n            if not valid_column(column_id):\n                return self._json(400,{\"error\":\"invalid column_id\"})\n            card={\"id\":uuid.uuid4().hex,\"title\":title.strip(),\"description\":description,\"column_id\":column_id}\n            state=load_state();state[\"cards\"].append(card);save_state(state)\n            return self._json(201,{\"card\":card})\n        move=re.fullmatch(r\"/api/cards/([^/]+)/move\",path)\n        if move:\n            card_id=move.group(1);state=load_state()\n            card=next((c for c in state[\"cards\"] if str(c.get(\"id\"))==card_id),None)\n            if card is None:return self._json(404,{\"error\":\"card not found\"})\n            column_id=body.get(\"column_id\")\n            if not valid_column(column_id):return self._json(400,{\"error\":\"invalid column_id\"})\n            card[\"column_id\"]=column_id;save_state(state)\n            return self._json(200,{\"card\":card})\n        return self._json(404,{\"error\":\"not found\"})\n    def do_PATCH(self):\n        path=urlparse(self.path).path\n        match=re.fullmatch(r\"/api/cards/([^/]+)\",path)\n        if not match:return self._json(404,{\"error\":\"not found\"})\n        try:body=self._body()\n        except (ValueError,UnicodeDecodeError) as exc:return self._json(400,{\"error\":str(exc)})\n        state=load_state();card=next((c for c in state[\"cards\"] if str(c.get(\"id\"))==match.group(1)),None)\n        if card is None:return self._json(404,{\"error\":\"card not found\"})\n        title=body.get(\"title\",card[\"title\"]);description=body.get(\"description\",card[\"description\"])\n        if not isinstance(title,str) or not title.strip() or len(title.strip())>160:return self._json(400,{\"error\":\"invalid title\"})\n        if not isinstance(description,str) or len(description)>1000:return self._json(400,{\"error\":\"invalid description\"})\n        card[\"title\"]=title.strip();card[\"description\"]=description;save_state(state)\n        return self._json(200,{\"card\":card})\n    def do_DELETE(self):\n        match=re.fullmatch(r\"/api/cards/([^/]+)\",urlparse(self.path).path)\n        if not match:return self._json(404,{\"error\":\"not found\"})\n        state=load_state();new_cards=[c for c in state[\"cards\"] if str(c.get(\"id\"))!=match.group(1)]\n        if len(new_cards)==len(state[\"cards\"]):return self._json(404,{\"error\":\"card not found\"})\n        state[\"cards\"]=new_cards;save_state(state)\n        return self._send(204,b\"\")\n    def log_message(self,format,*args):\n        super().log_message(format,*args)\n\ndef main():\n    parser=argparse.ArgumentParser()\n    parser.add_argument(\"--host\",default=\"127.0.0.1\")\n    parser.add_argument(\"--port\",type=int,required=True)\n    args=parser.parse_args()\n    HTTPServer((args.host,args.port),Handler).serve_forever()\n\nif __name__==\"__main__\":\n    main()\n"

class MockOllamaHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    tool_response_style = "native"
    plain_text_response = None
    def _json(self, doc):
        raw=json.dumps(doc).encode("utf-8")
        self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=="/api/version":return self._json({"version":"test-mock-1"})
        if self.path=="/api/tags":return self._json({"models":[{"name":"mock:latest","digest":"sha256:mock-model-fixture","details":{"family":"mock","parameter_size":"0","quantization_level":"none"}}]})
        self.send_error(404)
    def do_POST(self):
        if self.path!="/api/chat":return self.send_error(404)
        body=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
        if self.plain_text_response is not None:
            message={"role":"assistant","content":self.plain_text_response,"thinking":"MOCK_INTERNAL_THOUGHT_SENTINEL"}
            return self._json({"model":"mock:latest","created_at":"2026-01-01T00:00:00Z","message":message,"done":True,"done_reason":"stop","prompt_eval_count":10,"eval_count":3})
        messages=body.get("messages",[])
        count=sum(m.get("role")=="tool" for m in messages)
        if count==0:
            name="submit_plan";args={"plan":"Inspect the starter, implement the fixed local JSON API and basic browser interface, then run the compile check."}
        elif count==1:
            name="list_files";args={"path":"."}
        elif count==2:
            name="write_file";args={"path":"app.py","content":MOCK_APP_SOURCE}
        elif count==3:
            name="write_file";args={"path":"README.md","content":"# Mock board fixture\nRun with python app.py --host 127.0.0.1 --port PORT.\n"}
        elif count==4:
            name="run_check";args={"check":"compile"}
        elif count==5:
            name="finish";args={"summary":"Created a synthetic test fixture with the required JSON API and page hooks.","known_issues":["This is a mock-model fixture, not a scored agent result."],"checks_claimed":["compile"]}
        else:
            name="finish";args={"summary":"Synthetic pair fixture complete.","known_issues":[],"checks_claimed":[]}
        if self.tool_response_style == "fenced_json":
            fence = chr(96) * 3
            content = " " + fence + "json\n" + json.dumps({"name":name,"arguments":args}) + "\n" + fence + " "
            message = {"role":"assistant","content":content,"thinking":"MOCK_INTERNAL_THOUGHT_SENTINEL"}
        elif self.tool_response_style == "raw_json":
            message = {"role":"assistant","content":json.dumps({"name":name,"arguments":args}),"thinking":"MOCK_INTERNAL_THOUGHT_SENTINEL"}
        else:
            message = {"role":"assistant","content":"","thinking":"MOCK_INTERNAL_THOUGHT_SENTINEL","tool_calls":[{"function":{"name":name,"arguments":args}}]}
        self._json({"model":"mock:latest","created_at":"2026-01-01T00:00:00Z","message":message,"done":True,"done_reason":"stop","prompt_eval_count":10,"eval_count":3})
    def log_message(self,*args):
        pass


class ScriptedClient:
    """Deterministic in-process chat script for AgentLoop recovery tests."""
    def __init__(self, contents):
        self.contents = list(contents)
        self.requests = []

    def chat(self, request_body):
        self.requests.append(json.loads(json.dumps(request_body)))
        if not self.contents:
            raise AssertionError("scripted model response sequence was exhausted")
        content = self.contents.pop(0)
        return {
            "model":"mock:latest",
            "message":{"role":"assistant","content":content},
            "done":True,
            "done_reason":"stop",
            "prompt_eval_count":10,
            "eval_count":3,
        }


class AcceptanceSuiteTests(unittest.TestCase):
    def _run_scripted_agent(self, root, contents, max_turns=24):
        workspace = root / "workspace"
        workspace.mkdir()
        logger = RunLogger(
            root / "run-log",
            workspace,
            {
                "run_id":"recovery-test",
                "condition_label":"A",
                "task_brief_sha256":"0" * 64,
                "condition_config_sha256":"1" * 64,
                "logger_version":LOGGER_VERSION,
                "schema_version":SCHEMA_VERSION,
                "started_at_utc":utc_now(),
                "model":{"model_id":"mock:latest","model_digest":"sha256:mock"},
                "environment":{},
                "resource_limits":{},
                "base_commit":"test-fixture",
            },
        )
        client = ScriptedClient(contents)
        loop = AgentLoop(
            workspace=workspace,
            logger=logger,
            client=client,
            model_name="mock:latest",
            brief="Implement a tiny task board.",
            contract_json="{}",
            skill_text=None,
            condition_config_sha256="1" * 64,
            options={"temperature":0},
            max_turns=max_turns,
            max_tool_calls=20,
        )
        result = None
        error = None
        try:
            result = loop.run()
        except RunnerError as exc:
            error = str(exc)
        finally:
            logger.close()
        events = [json.loads(line) for line in (root / "run-log" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        return result, error, events, client, root / "run-log"

    def test_mock_application_passes_independent_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ws=root/"workspace";ws.mkdir();(ws/"app.py").write_text(MOCK_APP_SOURCE,encoding="utf-8")
            report=run_acceptance(ws,root/"acceptance")
            self.assertEqual(report["status"],"PASS",json.dumps(report,indent=2))
            self.assertEqual(report["failed"],0)
            self.assertGreaterEqual(report["passed"],7)

    def test_pair_runner_mock_model_logs_both_blind_runs_and_keeps_key_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); skill=root/"critical-thinking.md";skill.write_text("TEST SKILL SENTINEL: pause, inspect requirements, check edge cases, verify results.\n",encoding="utf-8")
            server=HTTPServer(("127.0.0.1",0),MockOllamaHandler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                base_url=f"http://127.0.0.1:{server.server_port}"
                output=root/"pair-output";key=root/"controller-key.json"
                report=run_pair(output,"mock:latest",skill,base_url=base_url,timeout=10,max_turns=10,max_tool_calls=20,key_file=key,allow_host_execution=True,allow_unpinned_skill=True)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)
            self.assertEqual(report["status"],"RUNS_COMPLETE",json.dumps(report,indent=2))
            self.assertTrue(key.is_file())
            self.assertFalse((output/"controller-private"/"condition-key.json").exists())
            mapping=json.loads(key.read_text(encoding="utf-8"))["condition_mapping"]
            self.assertEqual(set(mapping),{"A","B"})
            self.assertEqual({v for v in mapping.values()},{"skill_enabled","skill_disabled"})
            self.assertEqual(report["pair_log_validation"]["status"],"PASS",json.dumps(report["pair_log_validation"],indent=2))
            for label in ("A","B"):
                run=output/"runs"/f"run-{label.lower()}"
                self.assertEqual(report["per_run"][label]["agent_status"],"finished")
                self.assertEqual(report["per_run"][label]["acceptance_status"],"PASS")
                run_manifest=json.loads((run/"manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(run_manifest["model"]["model_digest"],"sha256:mock-model-fixture")
                rows=[json.loads(line) for line in (run/"events.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertTrue(any(e["event_type"]=="model_request" for e in rows))
                self.assertTrue(any(e["event_type"]=="model_response" for e in rows))
                self.assertTrue(any(e["event_type"]=="tool_call" for e in rows))
            enabled_label=next(label for label,cond in mapping.items() if cond=="skill_enabled")
            disabled_label=next(label for label,cond in mapping.items() if cond=="skill_disabled")
            enabled_reqs=list((output/"runs"/f"run-{enabled_label.lower()}"/"artifacts").glob("*model-request*.txt"))
            disabled_reqs=list((output/"runs"/f"run-{disabled_label.lower()}"/"artifacts").glob("*model-request*.txt"))
            self.assertTrue(any("TEST SKILL SENTINEL" in p.read_text(encoding="utf-8") for p in enabled_reqs))
            self.assertTrue(all("TEST SKILL SENTINEL" not in p.read_text(encoding="utf-8") for p in disabled_reqs))
            blinded=(output/"blinded-pair-report.json").read_text(encoding="utf-8")
            self.assertNotIn("skill_enabled",blinded)
            self.assertNotIn("skill_disabled",blinded)
            all_artifacts="".join(p.read_text(encoding="utf-8",errors="replace") for p in output.rglob("*") if p.is_file() and p.suffix not in {".zip"})
            self.assertNotIn("MOCK_INTERNAL_THOUGHT_SENTINEL",all_artifacts)
            for label in ("A","B"):
                packet=output/"score-packets"/f"score-{label}.zip"
                self.assertTrue(packet.is_file(),f"blind score packet missing: {packet}")
                with zipfile.ZipFile(packet) as archive:
                    names=set(archive.namelist())
                    self.assertTrue({"source/app.py","SCORING_RUBRIC.md","scorecard.schema.json","scorecard-template.json","observed-timeline.jsonl","acceptance-report.json"}.issubset(names))
                    contents="".join(archive.read(name).decode("utf-8",errors="replace") for name in names if not name.endswith(".zip"))
                    self.assertNotIn("TEST SKILL SENTINEL",contents)
                    self.assertNotIn("MOCK_INTERNAL_THOUGHT_SENTINEL",contents)
                    self.assertNotIn("skill_enabled",contents)
                    self.assertNotIn("skill_disabled",contents)
                    self.assertNotIn("condition_config_sha256",contents)
                    template=json.loads(archive.read("scorecard-template.json").decode("utf-8"))
                    self.assertEqual(template["blind_label"],label)
                    self.assertTrue(template["pair_id"].startswith("ctab-"))
                    timeline=[json.loads(line) for line in archive.read("observed-timeline.jsonl").decode("utf-8").splitlines() if line.strip()]
                    self.assertFalse(any(e["event_type"] in {"model_request","model_response"} for e in timeline))
            blinded_report=json.loads((output/"blinded-pair-report.json").read_text(encoding="utf-8"))
            self.assertEqual(blinded_report["instrumentation_gate"],"PASS")
            self.assertEqual(set(blinded_report["blind_score_packets"]),{"A","B"})
            for packet in blinded_report["blind_score_packets"].values():
                self.assertEqual(len(packet["sha256"]),64)


    def test_text_encoded_tool_call_parser_is_strict_and_allowlisted(self):
        call={"name":"submit_plan","arguments":{"plan":"inspect, implement, test"}}
        raw=json.dumps(call)
        fence=chr(96)*3
        fenced=fence+"json\n"+raw+"\n"+fence
        self.assertEqual(_parse_text_encoded_tool_call(raw),call)
        self.assertEqual(_parse_text_encoded_tool_call(fenced),call)
        self.assertEqual(_parse_text_encoded_tool_call(fence+"\n"+raw+"\n"+fence),call)
        invalid=[
            "The tool call is "+raw,
            raw+" I will now continue.",
            fence+"python\n"+raw+"\n"+fence,
            "{not valid JSON}",
            json.dumps({"name":"os.system","arguments":{"cmd":"anything"}}),
            json.dumps({"name":"write_file","arguments":["not","an","object"]}),
            json.dumps({"name":"write_file","arguments":{},"extra":"not allowed"}),
            None,
            42,
        ]
        for item in invalid:
            with self.subTest(item=item):
                self.assertIsNone(_parse_text_encoded_tool_call(item))

    def test_pair_runner_handles_fenced_content_tool_calls_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            skill=root/"critical-thinking.md"
            skill.write_text("TEST SKILL SENTINEL: pause, inspect requirements, check edge cases, verify results.\n",encoding="utf-8")
            server=HTTPServer(("127.0.0.1",0),MockOllamaHandler)
            previous_style=MockOllamaHandler.tool_response_style
            MockOllamaHandler.tool_response_style="fenced_json"
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                report=run_pair(root/"pair-output","mock:latest",skill,base_url=f"http://127.0.0.1:{server.server_port}",timeout=10,max_turns=10,max_tool_calls=20,key_file=root/"controller-key.json",allow_host_execution=True,allow_unpinned_skill=True)
            finally:
                MockOllamaHandler.tool_response_style=previous_style
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(report["status"],"RUNS_COMPLETE",json.dumps(report,indent=2))
            self.assertEqual(report["instrumentation_gate"],"PASS",json.dumps(report,indent=2))
            self.assertEqual(report["pair_log_validation"]["status"],"PASS")
            for label in ("A","B"):
                self.assertEqual(report["per_run"][label]["agent_status"],"finished")
                self.assertEqual(report["per_run"][label]["acceptance_status"],"PASS")
                run_dir=root/"pair-output"/"runs"/f"run-{label.lower()}"
                events=[json.loads(line) for line in (run_dir/"events.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertTrue(any(e["event_type"]=="plan_submitted" for e in events))
                self.assertTrue(any(e["event_type"]=="tool_call" for e in events))
                self.assertTrue(any(e["event_type"]=="file_changed" for e in events))
                responses=list((run_dir/"artifacts").glob("*model-response*.txt"))
                fence=chr(96)*3
                self.assertTrue(any(fence+"json" in p.read_text(encoding="utf-8") for p in responses))
                self.assertTrue((root/"pair-output"/"score-packets"/f"score-{label}.zip").is_file())

    def test_no_tool_response_recovers_when_next_response_calls_a_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contents = [
                "I will inspect the workspace and implement the board.",
                json.dumps({"name":"submit_plan","arguments":{"plan":"Inspect, implement, then verify."}}),
                json.dumps({"name":"write_file","arguments":{"path":"app.py","content":"print('ready')\n"}}),
                json.dumps({"name":"finish","arguments":{"summary":"Created a minimal file via the allowed tool.","known_issues":[],"checks_claimed":[]}}),
            ]
            result, error, events, client, run_dir = self._run_scripted_agent(root, contents)
            self.assertIsNone(error)
            self.assertEqual(result["status"],"finished")
            recoveries = [event for event in events if event["event_type"]=="agent_recovery_attempt"]
            self.assertEqual(len(recoveries),1)
            self.assertEqual(recoveries[0]["payload"]["attempt"],1)
            second_request = client.requests[1]
            recovery_prompts = [m.get("content","") for m in second_request["messages"] if m.get("role")=="user"]
            self.assertTrue(any("make one tool call now" in prompt.lower() for prompt in recovery_prompts))
            self.assertTrue(any("write_file" in prompt for prompt in recovery_prompts))
            self.assertTrue((root/"workspace"/"app.py").is_file())

    def test_text_encoded_tool_call_uses_explicit_user_tool_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contents = [
                json.dumps({"name":"submit_plan","arguments":{"plan":"Inspect, implement, verify."}}),
                json.dumps({"name":"list_files","arguments":{"path":"."}}),
                json.dumps({"name":"finish","arguments":{"summary":"Finished scripted test.","known_issues":[],"checks_claimed":[]}}),
            ]
            result, error, events, client, run_dir = self._run_scripted_agent(root, contents)
            self.assertIsNone(error)
            self.assertEqual(result["status"], "finished")
            second_request_messages = client.requests[1]["messages"]
            self.assertTrue(any(
                m.get("role") == "user" and "Tool result for submit_plan" in m.get("content", "")
                for m in second_request_messages
            ))
            self.assertFalse(any(
                m.get("role") == "tool" and m.get("tool_name") == "submit_plan"
                for m in second_request_messages
            ))
            event_types = {event["event_type"] for event in events}
            self.assertIn("model_request_started", event_types)
            self.assertIn("model_request_succeeded", event_types)
            self.assertTrue(any(event["event_type"] == "tool_call" for event in events))

    def test_model_request_timeout_is_logged_with_request_id_and_elapsed_time(self):
        class TimeoutClient(ScriptedClient):
            timeout = 12.0
            def chat(self, request_body):
                self.requests.append(json.loads(json.dumps(request_body)))
                raise TimeoutError("mock timeout")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            logger = RunLogger(root / "run-log", workspace, {
                "run_id":"timeout-test", "condition_label":"A", "task_brief_sha256":"0"*64,
                "condition_config_sha256":"1"*64, "logger_version":LOGGER_VERSION,
                "schema_version":SCHEMA_VERSION, "started_at_utc":utc_now(),
                "model":{"model_id":"mock:latest"}, "environment":{}, "resource_limits":{}, "base_commit":"test-fixture",
            })
            loop = AgentLoop(workspace, logger, TimeoutClient([]), "mock:latest", "brief", "{}", None,
                             "1"*64, {"temperature":0}, max_turns=2, max_tool_calls=4)
            try:
                with self.assertRaisesRegex(RunnerError, "model request failed on turn 1"):
                    loop.run()
            finally:
                logger.close()
            events = [json.loads(line) for line in (root / "run-log" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            failed = next(event for event in events if event["event_type"] == "model_request_failed")
            self.assertEqual(failed["payload"]["request_id"], "timeout-test-turn-001")
            self.assertEqual(failed["payload"]["failure_class"], "timeout")
            self.assertGreaterEqual(failed["payload"]["elapsed_ms"], 0)
            self.assertEqual(failed["payload"]["timeout_seconds"], 12.0)

    def test_repeated_echoed_tool_response_is_detected_and_original_exchanges_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            echoed = (
                "<tool_response>\n"
                '{"files":[{"path":"STARTER.md","size_bytes":238}],"truncated":false}'
                "\n</tool_response>\n\nThe workspace is minimal. I will use my original plan."
            )
            contents = [
                json.dumps({"name":"submit_plan","arguments":{"plan":"Inspect then implement."}}),
                json.dumps({"name":"list_files","arguments":{"path":"."}}),
                echoed,
                echoed,
            ]
            result, error, events, client, run_dir = self._run_scripted_agent(root, contents)
            self.assertIsNone(result)
            self.assertIn("repeated_identical_no_tool_response",error)
            self.assertEqual(len(client.requests),4)
            detections = [event for event in events if event["event_type"]=="agent_loop_detected"]
            self.assertEqual(len(detections),1)
            self.assertEqual(detections[0]["payload"]["reason"],"repeated_identical_no_tool_response")
            self.assertEqual(detections[0]["payload"]["turn"],4)
            archived_responses = list((run_dir/"artifacts").glob("*model-response*.txt"))
            saved_contents = [json.loads(path.read_text(encoding="utf-8"))["message"]["content"] for path in archived_responses]
            self.assertEqual(saved_contents.count(echoed),2)

    def test_changing_no_tool_responses_stop_at_bounded_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contents = [
                json.dumps({"name":"submit_plan","arguments":{"plan":"Inspect then implement."}}),
                "I'll implement the source now.",
                "The source should include a request handler.",
                "Next I will write the file.",
                "I am still planning the file.",
            ]
            result, error, events, client, run_dir = self._run_scripted_agent(root, contents, max_turns=24)
            self.assertIsNone(result)
            self.assertIn("consecutive_no_tool_response_limit",error)
            self.assertEqual(len(client.requests),5)
            detections = [event for event in events if event["event_type"]=="agent_loop_detected"]
            self.assertEqual(len(detections),1)
            self.assertEqual(detections[0]["payload"]["turn"],5)
            self.assertEqual(detections[0]["payload"]["consecutive_no_tool_responses"],4)

    def test_pair_report_records_loop_failure_without_using_full_turn_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root/"critical-thinking.md"
            skill.write_text("Test-only skill text.\n",encoding="utf-8")
            server = HTTPServer(("127.0.0.1",0),MockOllamaHandler)
            previous = MockOllamaHandler.plain_text_response
            MockOllamaHandler.plain_text_response = "Let's create the app.py file."
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                report = run_pair(
                    root/"pair-output",
                    "mock:latest",
                    skill,
                    base_url=f"http://127.0.0.1:{server.server_port}",
                    timeout=10,
                    max_turns=24,
                    max_tool_calls=20,
                    key_file=root/"controller-key.json",
                    allow_host_execution=True,
                    allow_unpinned_skill=True,
                )
            finally:
                MockOllamaHandler.plain_text_response = previous
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(report["status"],"RUN_INCOMPLETE")
            for label in ("A","B"):
                self.assertEqual(report["per_run"][label]["agent_status"],"failed")
                self.assertTrue(any("repeated_identical_no_tool_response" in error for error in report["per_run"][label]["errors"]))
                run_dir = root/"pair-output"/"runs"/f"run-{label.lower()}"
                events = [json.loads(line) for line in (run_dir/"events.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertTrue(any(event["event_type"]=="agent_loop_detected" for event in events))
                self.assertEqual(len(list((run_dir / "artifacts").glob("*model-response*.txt"))), 2)
            self.assertNotEqual(report["instrumentation_gate"],"PASS")

    def test_pinned_critical_thinking_skill_source_rejects_substitution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            skill=root/"different-skill.md"
            skill.write_text("not the pinned Critical Thinking skill",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"pinned source"):
                run_pair(root/"output","no-model-needed:latest",skill,allow_host_execution=True)
            spec=json.loads((Path(__file__).with_name("skill_source.json")).read_text(encoding="utf-8"))
            self.assertEqual(spec["repository"],"memoryprismv1/cognitive-interface-ai-skills")
            self.assertEqual(spec["path"],"critical-thinking/SKILL.md")
            self.assertEqual(spec["commit"],"d1f23e2ad9dafd323940fc6b7a00f1700275d885")
            self.assertEqual(spec["git_blob_sha1"],"d7134969b124e39c04e343bed2ce2475f64b9a64")

    def test_remote_or_non_http_ollama_endpoint_is_refused(self):
        for value in ["https://example.com:11434","http://192.168.1.10:11434","file:///tmp/test","http://127.0.0.1"]:
            with self.assertRaises(ValueError):
                OllamaClient(value)

if __name__=="__main__":
    unittest.main()
