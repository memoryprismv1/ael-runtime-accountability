"""Local Ollama tool runner for the CT A/B software-build task.

The runner, event logger, task brief, acceptance suite and score report remain
outside agent-writable workspaces. Only enumerated workspace/file/check tools
are exposed to the model; no arbitrary shell command tool is provided.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping
from .logger import LOGGER_VERSION, RunLogger, sha256_bytes, utc_now

AGENT_TOOL_VERSION = "0.1.0"
MAX_READ_BYTES = 160_000
MAX_WRITE_BYTES = 220_000
MAX_FILES = 100
MAX_TURNS = 36
MAX_CONSECUTIVE_NO_TOOL_RESPONSES = 4
MAX_IDENTICAL_NO_TOOL_RESPONSES = 2

BASE_SYSTEM = """You are implementing a small single-user local Kanban web application for a client.
Follow the supplied client brief and API contract exactly. Start by calling submit_plan with a short actionable implementation plan. Then inspect the starter workspace; write original code; run the available controlled checks; fix failures; and call finish with a factual summary and known limitations.
Available tools are the only way to inspect/edit the workspace or run checks. There is no arbitrary shell command tool. Do not ask for or reveal hidden chain-of-thought. submit_plan and the concise finish summary are task artifacts, not internal reasoning. Never claim a check passed unless its captured result shows it passed.
The application must be built from scratch; do not copy Trello code, brand assets or distinctive styling. Keep work limited to the small local application in the brief.
"""


def _no_tool_recovery_instruction(plan_submitted: bool) -> str:
    """Ask for one concrete tool action after an assistant response without a tool call."""
    plan_note = (
        "The implementation plan has already been accepted; do not submit it again. "
        if plan_submitted
        else "Submit a brief plan first if you have not done so yet. "
    )
    return (
        "Your previous message did not invoke an available tool. "
        "Do not repeat explanations, quote previous tool output, or restate your plan. "
        "Make one tool call now. "
        + plan_note
        + "Allowed tools and argument shapes: "
        'submit_plan({"plan":"..."}); '
        'list_files({"path":"."}); '
        'read_file({"path":"STARTER.md"}); '
        'write_file({"path":"app.py","content":"complete source code"}); '
        'run_check({"check":"compile"}) or run_check({"check":"unit_tests"}); '
        'finish({"summary":"...","known_issues":[],"checks_claimed":[]}). '
        'Use a native tool call or put exactly one JSON object in message content with only the keys '
        '"name" and "arguments" and no surrounding prose or code fence. '
        "Prefer the next concrete inspection or implementation action; call finish only when the work is complete."
    )

def _parse_text_encoded_tool_call(content: Any) -> dict[str, Any] | None:
    """Parse only a single allowlisted tool-call JSON object from message.content.

    Some Ollama-served models describe calls as JSON in the content field
    instead of using the native tool_calls field. Accept only an exact JSON
    object, either raw or enclosed in one optional JSON code fence. Do not
    scrape JSON out of prose or execute arbitrary model-provided text.
    """
    if not isinstance(content, str):
        return None
    candidate = content.strip()
    fenced = re.fullmatch(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```[ \t]*", candidate, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    # Reject any prose/fences around a JSON object; json.loads must consume all.
    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict) or set(parsed) != {"name", "arguments"}:
        return None
    name = parsed.get("name")
    arguments = parsed.get("arguments")
    allowlist = {item["function"]["name"] for item in TOOLS}
    if not isinstance(name, str) or name not in allowlist:
        return None
    if not isinstance(arguments, dict):
        return None
    return {"name": name, "arguments": arguments}


TOOLS = [
    {"type":"function","function":{"name":"submit_plan","description":"Submit a brief implementation plan before editing files. Use once near the start.","parameters":{"type":"object","properties":{"plan":{"type":"string","minLength":1}},"required":["plan"]}}},
    {"type":"function","function":{"name":"list_files","description":"List relative file paths under the project workspace.","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}}}}},
    {"type":"function","function":{"name":"read_file","description":"Read a UTF-8 text file within the project workspace.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"Create or replace a UTF-8 text file within the project workspace. Use original project files only; do not access paths outside the workspace.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"run_check","description":"Run one controlled check. compile runs Python compileall. unit_tests runs the project's own tests. No arbitrary command is accepted.","parameters":{"type":"object","properties":{"check":{"type":"string","enum":["compile","unit_tests"]}},"required":["check"]}}},
    {"type":"function","function":{"name":"finish","description":"Finish the implementation. State what was built, which checks were run, outcomes, and known limitations. Do not claim independent acceptance has run.","parameters":{"type":"object","properties":{"summary":{"type":"string"},"known_issues":{"type":"array","items":{"type":"string"}},"checks_claimed":{"type":"array","items":{"type":"string"}}},"required":["summary","known_issues","checks_claimed"]}}}
]


class RunnerError(RuntimeError):
    pass


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_path(root: Path, raw: str, allow_root: bool = False) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("path must be a non-empty relative string")
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts or raw in {".", "./"} and not allow_root:
        raise ValueError("absolute paths, '..', and workspace root are not valid file paths")
    if any(part in {".git", "__pycache__", ".venv", "venv"} for part in rel.parts):
        raise ValueError("internal/runtime directories cannot be accessed")
    target = (root / rel).resolve(strict=False)
    if not _within(target, root):
        raise ValueError("path resolves outside workspace")
    # Resolve each existing parent to reject symlink traversal, not just literal '..'.
    cur = root
    for part in rel.parts[:-1]:
        cur = cur / part
        if cur.exists() and cur.is_symlink():
            raise ValueError("symlinked parent paths are not allowed")
    if target.exists() and target.is_symlink():
        raise ValueError("symlink targets are not allowed")
    return target


def _local_host(base_url: str) -> bool:
    from urllib.parse import urlparse
    p = urlparse(base_url)
    return p.scheme == "http" and p.hostname in {"127.0.0.1", "localhost", "::1"} and p.port is not None and p.username is None and p.password is None


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 180.0):
        if not _local_host(base_url):
            raise ValueError("only an explicit http loopback Ollama URL is allowed")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.version = "unavailable"

    def _get_json(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(self.base_url + path, method="GET")
        with urllib.request.urlopen(req, timeout=min(self.timeout, 10.0)) as response:
            obj = json.loads(response.read().decode("utf-8"))
        if not isinstance(obj, dict):
            raise RunnerError(f"Ollama {path} response was not a JSON object")
        return obj

    def info(self) -> dict[str, Any]:
        version_doc = self._get_json("/api/version")
        self.version = str(version_doc.get("version", "unknown"))
        return version_doc

    def list_models(self) -> list[dict[str, Any]]:
        obj = self._get_json("/api/tags")
        models = obj.get("models")
        if not isinstance(models, list):
            raise RunnerError("Ollama /api/tags response has no models array")
        return [m for m in models if isinstance(m, dict)]

    def chat(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        data = json.dumps(dict(request_body), ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base_url + "/api/chat", data=data, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            obj = json.loads(response.read().decode("utf-8"))
        if not isinstance(obj, dict) or not isinstance(obj.get("message"), dict):
            raise RunnerError("Ollama /api/chat response is missing the message object")
        return obj


class AgentLoop:
    def __init__(self, workspace: str | Path, logger: RunLogger, client: OllamaClient, model_name: str,
                 brief: str, contract_json: str, skill_text: str | None, condition_config_sha256: str,
                 options: Mapping[str, Any], max_turns: int = MAX_TURNS, max_tool_calls: int = 100):
        self.workspace = Path(workspace).resolve(strict=True)
        self.logger = logger
        self.client = client
        self.model_name = model_name
        self.skill_text = skill_text
        self.condition_config_sha256 = condition_config_sha256
        self.options = dict(options)
        self.max_turns = max_turns
        self.max_tool_calls = max_tool_calls
        self.tool_calls = 0
        self.plan_submitted = False
        self.finished = False
        self.finish_args: dict[str, Any] | None = None
        self.request_counter = 0
        self.consecutive_no_tool_responses = 0
        self.last_no_tool_fingerprint: str | None = None
        self.identical_no_tool_responses = 0
        system = BASE_SYSTEM
        if skill_text is not None:
            system += "\n\n=== CRITICAL THINKING SKILL (verbatim supplied file) ===\n" + skill_text + "\n=== END CRITICAL THINKING SKILL ===\n"
        self.messages: list[dict[str, Any]] = [
            {"role":"system","content":system},
            {"role":"user","content":"Client brief follows:\n\n" + brief + "\n\nAPI contract (JSON):\n" + contract_json + "\n\nThe starter workspace initially contains only STARTER.md. Begin by calling submit_plan."}
        ]

    def _list_files(self, args: dict[str, Any]) -> dict[str, Any]:
        raw = args.get("path", ".")
        target = self.workspace if raw in {".", "./", ""} else _safe_path(self.workspace, raw)
        if not target.exists() or not target.is_dir():
            raise ValueError("directory does not exist")
        ignored = {".git", "__pycache__", ".venv", "venv", "node_modules"}
        results = []
        for p in sorted(target.rglob("*")):
            if any(part in ignored for part in p.relative_to(self.workspace).parts):
                continue
            if p.is_file():
                results.append({"path":p.relative_to(self.workspace).as_posix(),"size_bytes":p.stat().st_size})
                if len(results) > MAX_FILES:
                    return {"files":results[:MAX_FILES],"truncated":True}
        return {"files":results,"truncated":False}

    def _read_file(self, args: dict[str, Any]) -> dict[str, Any]:
        path = _safe_path(self.workspace, args.get("path", ""))
        if not path.is_file():
            raise FileNotFoundError("file does not exist")
        raw = path.read_bytes()
        if len(raw) > MAX_READ_BYTES:
            raise ValueError(f"file exceeds {MAX_READ_BYTES} byte read limit")
        text = raw.decode("utf-8")
        return {"path":path.relative_to(self.workspace).as_posix(),"content":text,"size_bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}

    def _write_file(self, args: dict[str, Any]) -> dict[str, Any]:
        rel = args.get("path")
        content = args.get("content")
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        raw = content.encode("utf-8")
        if len(raw) > MAX_WRITE_BYTES:
            raise ValueError(f"file exceeds {MAX_WRITE_BYTES} byte write limit")
        path = _safe_path(self.workspace, rel)
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        # Re-check after directory creation; reject races and symlinks.
        path = _safe_path(self.workspace, rel)
        if not path.exists() and len([p for p in self.workspace.rglob("*") if p.is_file()]) >= MAX_FILES:
            raise ValueError(f"workspace may contain no more than {MAX_FILES} files")
        path.write_bytes(raw)
        return {"path":path.relative_to(self.workspace).as_posix(),"size_bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"action":"created_or_replaced"}

    def _run_check(self, args: dict[str, Any]) -> dict[str, Any]:
        check = args.get("check")
        if check == "compile":
            command = [sys.executable, "-m", "compileall", "-q", "."]
        elif check == "unit_tests":
            tests_dir = self.workspace / "tests"
            if not tests_dir.is_dir() or not any(t.is_file() and t.suffix == ".py" for t in tests_dir.rglob("*")):
                return {"status":"failed","reason":"No project Python tests found under tests/; refusing to report an empty test run as success."}
            command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
        else:
            raise ValueError("only compile and unit_tests are available")
        before = self.logger.snapshot_workspace()
        started = time.monotonic()
        try:
            proc = self.logger.run_command(command, self.workspace, "verification", timeout_seconds=30.0, env=_controlled_subprocess_env())
        except subprocess.TimeoutExpired:
            return {"status":"failed","check":check,"reason":"controlled check timed out after 30 seconds"}
        elapsed = round(time.monotonic()-started, 3)
        status = "passed" if proc.returncode == 0 else "failed"
        self.logger.record_test_result(command, proc.returncode, None, None)
        return {"status":status,"check":check,"exit_code":proc.returncode,"elapsed_seconds":elapsed,"stdout_tail":proc.stdout[-5000:],"stderr_tail":proc.stderr[-5000:]}

    def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "submit_plan":
            if self.plan_submitted:
                raise ValueError("plan may be submitted only once")
            plan = args.get("plan")
            if not isinstance(plan, str) or not plan.strip():
                raise ValueError("plan must be non-empty text")
            self.plan_submitted = True
            self.logger.record_agent_plan(plan)
            return {"accepted":True,"note":"Plan saved as agent-declared evidence. Proceed to inspect and implement."}
        if name == "list_files":
            return self._list_files(args)
        if name == "read_file":
            return self._read_file(args)
        if name == "write_file":
            return self._write_file(args)
        if name == "run_check":
            return self._run_check(args)
        if name == "finish":
            if not self.plan_submitted:
                raise ValueError("submit a plan before finishing")
            summary = args.get("summary")
            issues = args.get("known_issues", [])
            checks = args.get("checks_claimed", [])
            if not isinstance(summary,str) or not isinstance(issues,list) or not isinstance(checks,list):
                raise ValueError("invalid finish payload")
            self.finish_args = {"summary":summary,"known_issues":issues,"checks_claimed":checks}
            self.logger.capture_artifact("agent-final-summary.json",json.dumps(self.finish_args,indent=2,ensure_ascii=False),"application/json")
            self.logger.emit("agent_note","agent","delivery","declared",{"note_type":"final_summary","claimed_checks":checks,"known_issue_count":len(issues)})
            self.finished=True
            return {"finished":True}
        raise ValueError(f"unknown tool: {name}")

    def run(self) -> dict[str, Any]:
        for turn in range(1,self.max_turns+1):
            self.request_counter += 1
            request_id = f"{self.logger.run_id}-turn-{turn:03d}"
            request_body = {
                "model":self.model_name,"messages":self.messages,"tools":TOOLS,"stream":False,
                "options":self.options,"think":False,
            }
            began=time.monotonic()
            try:
                response=self.client.chat(request_body)
            except (OSError, urllib.error.URLError, TimeoutError, ValueError, RunnerError) as exc:
                self.logger.emit("error","runtime","implementation","observed",{"kind":"model_request_failed","turn":turn,"error_type":type(exc).__name__,"message":str(exc)[:1000]})
                raise RunnerError(f"model request failed on turn {turn}: {exc}") from exc
            elapsed_ms=round((time.monotonic()-began)*1000,3)
            message=response.get("message",{})
            # Some local models expose a separate "thinking" field. It is
            # explicitly excluded from logs and conversational history.
            safe_message={k:v for k,v in message.items() if k not in {"thinking","reasoning","analysis"}}
            safe_response={k:v for k,v in response.items() if k not in {"thinking","reasoning","analysis"}}
            safe_response["message"] = safe_message
            payload_text=json.dumps(request_body,ensure_ascii=False,sort_keys=True)
            response_text=json.dumps(safe_response,ensure_ascii=False,sort_keys=True)
            self.logger.record_model_exchange(
                {"provider":"ollama-local","model_id":self.model_name,"request_id":request_id,"latency_ms":elapsed_ms,"finish_reason":response.get("done_reason"),"condition_config_sha256":self.condition_config_sha256},
                payload_text,response_text,
                {"prompt_tokens":response.get("prompt_eval_count"),"completion_tokens":response.get("eval_count")},
                phase="implementation"
            )
            tool_calls=safe_message.get("tool_calls",[])
            # Prefer Ollama's native structured tool calls. A narrow fallback
            # handles models that encode one call as raw/fenced JSON content.
            assistant_entry={"role":"assistant","content":safe_message.get("content","") or ""}
            if isinstance(tool_calls,list) and tool_calls:
                assistant_entry["tool_calls"]=tool_calls
            else:
                text_call=_parse_text_encoded_tool_call(safe_message.get("content",""))
                if text_call is not None:
                    tool_calls=[{"function":{"name":text_call["name"],"arguments":text_call["arguments"]}}]
                    # Keep the normalized call in dialogue history; the original
                    # response text remains unchanged in the audit artifact.
                    assistant_entry={"role":"assistant","content":"","tool_calls":tool_calls}
                else:
                    self.messages.append(assistant_entry)
                    self.logger.emit("error","runtime","implementation","observed",{"kind":"model_response_without_tool_call","turn":turn})
                    content = safe_message.get("content","") or ""
                    fingerprint = hashlib.sha256(" ".join(content.split()).encode("utf-8")).hexdigest()
                    if fingerprint == self.last_no_tool_fingerprint:
                        self.identical_no_tool_responses += 1
                    else:
                        self.identical_no_tool_responses = 1
                    self.last_no_tool_fingerprint = fingerprint
                    self.consecutive_no_tool_responses += 1

                    loop_reason = None
                    if self.identical_no_tool_responses >= MAX_IDENTICAL_NO_TOOL_RESPONSES:
                        loop_reason = "repeated_identical_no_tool_response"
                    elif self.consecutive_no_tool_responses >= MAX_CONSECUTIVE_NO_TOOL_RESPONSES:
                        loop_reason = "consecutive_no_tool_response_limit"

                    if loop_reason:
                        self.logger.emit(
                            "agent_loop_detected","runner","implementation","failed",
                            {
                                "reason":loop_reason,
                                "turn":turn,
                                "consecutive_no_tool_responses":self.consecutive_no_tool_responses,
                                "identical_response_count":self.identical_no_tool_responses,
                                "response_sha256":fingerprint,
                                "tool_call_observed":False,
                            },
                        )
                        raise RunnerError(
                            f"agent no-tool loop detected: {loop_reason}; stopped at turn {turn} "
                            f"(consecutive_no_tool_responses={self.consecutive_no_tool_responses}, "
                            f"identical_response_count={self.identical_no_tool_responses})"
                        )

                    self.logger.emit(
                        "agent_recovery_attempt","runner","implementation","requested",
                        {
                            "turn":turn,
                            "attempt":self.consecutive_no_tool_responses,
                            "reason":"model_response_without_tool_call",
                            "response_sha256":fingerprint,
                            "next_action":"send_explicit_tool-call recovery instruction",
                        },
                    )
                    self.messages.append({"role":"user","content":_no_tool_recovery_instruction(self.plan_submitted)})
                    continue
            self.consecutive_no_tool_responses = 0
            self.last_no_tool_fingerprint = None
            self.identical_no_tool_responses = 0
            self.messages.append(assistant_entry)
            for call in tool_calls:
                self.tool_calls += 1
                if self.tool_calls > self.max_tool_calls:
                    raise RunnerError("maximum tool call budget exceeded")
                function=call.get("function",{}) if isinstance(call,dict) else {}
                name=function.get("name")
                arguments=function.get("arguments",{})
                if isinstance(arguments,str):
                    try: arguments=json.loads(arguments)
                    except json.JSONDecodeError: arguments={}
                if not isinstance(arguments,dict):
                    arguments={}
                call_id=f"call-{self.tool_calls:03d}"
                before = self.logger.snapshot_workspace() if name == "write_file" else None
                try:
                    outcome=self.dispatch(str(name),arguments)
                    status="succeeded"
                except Exception as exc:
                    outcome={"error":type(exc).__name__,"message":str(exc)[:1500]}
                    status="failed"
                self.logger.record_tool_call(str(name),call_id,arguments,outcome,status=status,phase="implementation")
                if before is not None:
                    self.logger.record_file_changes(before,self.logger.snapshot_workspace())
                if name=="finish" and status=="succeeded" and self.finished:
                    return {"status":"finished","turns":turn,"tool_calls":self.tool_calls,"finish":self.finish_args}
                self.messages.append({"role":"tool","tool_name":str(name),"content":json.dumps(outcome,ensure_ascii=False,sort_keys=True)})
        raise RunnerError(f"agent did not call finish within {self.max_turns} turns")


def _controlled_subprocess_env() -> dict[str,str]:
    """Keep subprocess env small while preserving Python execution on Windows/Linux."""
    allowed = {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","TMPDIR","PATHEXT","SYSTEMDRIVE","COMSPEC","LANG","LC_ALL","PYTHONPATH"}
    env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
    env["PYTHONDONTWRITEBYTECODE"]="1"
    return env
