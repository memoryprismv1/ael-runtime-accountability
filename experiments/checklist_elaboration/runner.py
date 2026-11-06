"""Planning-only checklist-elaboration runner."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import random
import secrets
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Mapping
from testing_logger.logger import TestingLogger, LOGGER_VERSION, SCHEMA_VERSION, canonical_json, sha256_bytes, sha256_file, utc_now
from experiments.ct_ab.agent_loop import OllamaClient
from experiments.ct_ab.validate_log import LogValidationError, validate_run

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_TASK = PACKAGE_DIR / "task-v1"
MP_COMMIT = "5cc48df650b1942412047ee6e82642c14e800967"
CT_COMMIT = "8152c98d2e388735d8bf63857b46a2056ef0a967"
MP_FILES = {
 "skill/SKILL.md":"8208fdfb794a2cf78c2b1a310912eddfc2dc80a5",
 "skill/references/starter-kit.md":"07c6594a41ce05f7d06b14c59770d78775983520",
 "skill/references/source-corpus/README.md":"12488f8a6ef2b48766d7c6ffabfa979ac116a046",
 "skill/references/source-corpus/Memory-Prism-Framework.md":"04d98b8b22bdce03ed63c6de85201924db1008ae",
 "skill/references/source-corpus/foundations/Audits.md":"c4e46ba51bae0ce6608fa949b5e5f84fe639fb2c",
 "skill/references/source-corpus/foundations/Boards.md":"d4b80e0c770a2663a569cfacf46170c0d7e86986",
 "skill/references/source-corpus/foundations/Flow-under-Constraint.md":"f272cce5da10ef69d5fdad79a8c6ed055cf90251",
 "skill/references/source-corpus/foundations/Identity.md":"6780c1a607341f407ac3a76f31a38d1f2d82f1c4",
 "skill/references/source-corpus/supplementary/Accumulation-Patterns.md":"4f55b86ee5c40c8c1707e2466c8fba02f4cc9a3c",
 "skill/references/source-corpus/supplementary/No-Sacred-States.md":"da7d2da1263db69d2882fccb61b0bb9ede9bd483",
 "skill/references/source-corpus/supplementary/Working-Lines.md":"e99fadcac90a01af4b0c9263161640277d4a2846",
}
CT_FILES = {
 "critical-thinking/SKILL.md":"0bd33321e535d9e68469307f2128cf27637046c9",
 "critical-thinking/MEMORY-PRISM-CHECKLIST.md":"8f12af7020757250c5decff0ba13ed75f0279b04",
 "critical-thinking/MEMORY-PRISM-REFERENCE.md":"eba72fd05d6758b2f88ecf1435f541e87fd3a8fe",
}
MAX_READ=160000
MAX_WRITE=220000
MAX_TURNS=48
MAX_TOOLS=120
MAX_REQUEST_SECONDS=600
MAX_RUN_SECONDS=2700
MAX_OUTPUT_TOKENS=4000
SYSTEM = """You are preparing an actionable pilot plan from a fixed task and evidence pack.
Read task/TASK.md and inspect source-pack/ files before declaring anything unavailable. Optional skill packages, if present, are under skills/. Read relevant supplied skill material.
Create three files under deliverables/: plan.md, consideration-register.json, and open-decisions.md. Distinguish facts, inferences, assumptions and unresolved decisions.
No real user, sponsor, or human is available. Do not contact anyone or wait for a reply. request_input only records a hypothetical question and immediately returns no answer; it contacts nobody. Use it only for a genuinely unavailable external project input after checking the files. Continue independently.
Resolve what can be resolved from the files. Use bounded assumptions only where safe. Defer genuinely unavailable decisions to the appropriate project role without blocking unrelated work. Never invent operational policies, authority, thresholds, guarantees or source-of-truth rules.
Tools are the only way to inspect and write files. No shell, browser, internet, package installation, arbitrary execution or live messaging is available. Do not reveal hidden chain-of-thought. Finish only after all three deliverables are written and valid."""
TOOLS = [
 {"type":"function","function":{"name":"list_files","description":"List supplied task, source-pack, skill and deliverables files.","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}}}}},
 {"type":"function","function":{"name":"read_file","description":"Read a supplied UTF-8 file.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
 {"type":"function","function":{"name":"write_file","description":"Write only beneath deliverables/.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
 {"type":"function","function":{"name":"request_input","description":"Record a hypothetical external project question. No person is contacted and no answer is returned.","parameters":{"type":"object","properties":{"question":{"type":"string"},"why_needed":{"type":"string"},"project_role":{"type":"string"}},"required":["question","why_needed","project_role"]}}},
 {"type":"function","function":{"name":"finish","description":"Finish after all three deliverables are valid.","parameters":{"type":"object","properties":{"summary":{"type":"string"},"known_limitations":{"type":"array","items":{"type":"string"}}},"required":["summary","known_limitations"]}}},
]
ALLOWED={x["function"]["name"] for x in TOOLS}
REQUIRED=("plan.md","consideration-register.json","open-decisions.md")
REGISTER_FIELDS={"id","statement","category","source_type","evidence","why_it_matters","disposition","action","plan_effect"}
class RunnerError(RuntimeError):
    pass

def safe_path(root:Path, raw:Any)->Path:
    if not isinstance(raw,str) or not raw.strip(): raise ValueError("path must be non-empty text")
    rel=Path(raw)
    if rel.is_absolute() or ".." in rel.parts: raise ValueError("absolute paths and parent traversal are forbidden")
    if any(x in {".git","__pycache__",".venv","venv","node_modules"} for x in rel.parts): raise ValueError("internal paths unavailable")
    target=(root/rel).resolve(strict=False); target.relative_to(root.resolve(strict=True))
    cur=root.resolve(strict=True)
    for part in rel.parts:
        cur=cur/part
        if cur.exists() and cur.is_symlink(): raise ValueError("symlink traversal forbidden")
    return target

def tree_sha(root:Path)->str:
    h=hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        n=p.relative_to(root).as_posix().encode(); b=p.read_bytes()
        h.update(len(n).to_bytes(4,"big")); h.update(n); h.update(len(b).to_bytes(8,"big")); h.update(b)
    return h.hexdigest()

def git(root:Path,*args:str)->str:
    p=subprocess.run(["git","-C",str(root),*args],check=True,capture_output=True,text=True,timeout=10)
    return p.stdout.strip()

def verify_source(root:str|Path,commit:str,files:Mapping[str,str])->dict[str,Any]:
    base=Path(root).resolve(strict=True)
    if git(base,"rev-parse","HEAD")!=commit: raise ValueError(f"skill checkout must be pinned at {commit}")
    if git(base,"status","--porcelain","--untracked-files=all"): raise ValueError("skill checkout must be clean")
    result={}
    for rel,want in files.items():
        actual=git(base,"rev-parse",f"{commit}:{rel}")
        if actual!=want: raise ValueError(f"Git blob mismatch for {rel}")
        p=(base/rel).resolve(strict=True); p.relative_to(base)
        result[rel]={"git_blob_sha1":actual,"sha256":sha256_file(p),"size_bytes":p.stat().st_size}
    return {"commit":commit,"files":result}

def verify_task_fixture(task_dir:str|Path)->dict[str,Any]:
    root=Path(task_dir).resolve(strict=True)
    manifest=json.loads((root/"fixture-manifest.json").read_text(encoding="utf-8"))
    expected=manifest.get("source_files")
    if not isinstance(expected,dict) or not expected:
        raise ValueError("task fixture manifest has no source_files map")
    actual_paths={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name!="fixture-manifest.json"}
    if actual_paths!=set(expected):
        raise ValueError("task fixture files differ from the pinned v1 inventory")
    verified={}
    for rel,want in expected.items():
        raw=(root/rel).read_bytes()
        blob=hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+bytes([0])+raw).hexdigest()
        if blob!=want:
            raise ValueError(f"task fixture Git blob mismatch: {rel}")
        verified[rel]={"git_blob_sha1":blob,"size_bytes":len(raw),"sha256":sha256_bytes(raw)}
    return {"fixture_id":manifest.get("fixture_id"),"files":verified,"tree_sha256":tree_sha(root)}

def copy_readonly(src:Path,dst:Path)->None:
    if not src.is_file() or src.is_symlink(): raise ValueError(f"required source unavailable: {src}")
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst); dst.chmod(0o444)

def prepare_workspace(task_dir:str|Path,workspace:str|Path,*,mp_source:str|Path|None,ct_source:str|Path|None,mp_enabled:bool,ct_enabled:bool)->dict[str,Any]:
    task=Path(task_dir).resolve(strict=True)
    if not (task/"TASK.md").is_file() or not (task/"source-pack").is_dir(): raise ValueError("task fixture requires TASK.md and source-pack/")
    root=Path(workspace).resolve()
    if root.exists() and any(root.iterdir()): raise FileExistsError("workspace must be new or empty")
    root.mkdir(parents=True,exist_ok=True); (root/"task").mkdir()
    copy_readonly(task/"TASK.md",root/"task"/"TASK.md")
    if (task/"README.md").is_file(): copy_readonly(task/"README.md",root/"task"/"README.md")
    shutil.copytree(task/"source-pack",root/"source-pack")
    for p in (root/"source-pack").rglob("*"):
        if p.is_symlink(): raise ValueError("source pack cannot contain symlinks")
        if p.is_file(): p.chmod(0o444)
    skills={"memory_prism":None,"critical_thinking":None}
    if mp_enabled:
        skills["memory_prism"]=verify_source(mp_source,MP_COMMIT,MP_FILES)
        dest=root/"skills"/"memory-prism"
        for rel in MP_FILES: copy_readonly(Path(mp_source)/rel,dest/Path(rel).relative_to("skill"))
    if ct_enabled:
        skills["critical_thinking"]=verify_source(ct_source,CT_COMMIT,CT_FILES)
        dest=root/"skills"/"critical-thinking"
        for rel in CT_FILES: copy_readonly(Path(ct_source)/rel,dest/Path(rel).name)
    (root/"deliverables").mkdir()
    return {"task_sha256":tree_sha(task),"visible_inputs_sha256":tree_sha(root),"skills":skills}

def validate_outputs(workspace:str|Path)->dict[str,Any]:
    root=Path(workspace).resolve(strict=True); out=root/"deliverables"
    if not out.is_dir() or out.is_symlink(): raise ValueError("deliverables/ missing")
    results={}; total=0
    for name in REQUIRED:
        p=safe_path(root,"deliverables/"+name)
        if not p.is_file(): raise ValueError(f"missing {name}")
        raw=p.read_bytes()
        if not raw.strip() or len(raw)>MAX_WRITE: raise ValueError(f"empty or oversized {name}")
        total+=len(raw); results[name]={"size_bytes":len(raw),"sha256":sha256_bytes(raw)}
    try: register=json.loads((out/"consideration-register.json").read_text(encoding="utf-8"))
    except Exception as exc: raise ValueError(f"invalid consideration JSON: {exc}") from exc
    if not isinstance(register,dict) or not isinstance(register.get("items"),list): raise ValueError("consideration register needs items array")
    seen=set()
    for i,item in enumerate(register["items"]):
        if not isinstance(item,dict) or REGISTER_FIELDS-set(item): raise ValueError(f"consideration item {i} missing fields")
        if not isinstance(item["id"],str) or not item["id"].strip() or item["id"] in seen: raise ValueError(f"consideration item {i} has empty/duplicate id")
        seen.add(item["id"])
        for field in ("statement","category","source_type","why_it_matters","disposition","action","plan_effect"):
            if not isinstance(item[field],str) or not item[field].strip(): raise ValueError(f"item {i}: {field} must be text")
    if total>1000000: raise ValueError("deliverables exceed total byte limit")
    return {"status":"PASS","files":results,"consideration_count":len(register["items"]),"total_bytes":total}


def parse_args(value:Any)->dict[str,Any]:
    if isinstance(value,dict): return dict(value)
    if isinstance(value,str):
        parsed=json.loads(value)
        if isinstance(parsed,dict): return parsed
    raise ValueError("tool arguments must be an object")

def parse_text_call(value:Any)->list[dict[str,Any]]:
    if not isinstance(value,str): return []
    raw=value.strip()
    if raw.startswith(chr(96)*3):
        lines=raw.splitlines()
        if len(lines)>=3 and lines[-1].strip()==chr(96)*3: raw="\n".join(lines[1:-1]).strip()
    try: obj=json.loads(raw)
    except json.JSONDecodeError: return []
    if not isinstance(obj,dict) or set(obj)!={"name","arguments"} or obj["name"] not in ALLOWED or not isinstance(obj["arguments"],dict): return []
    return [{"id":"text-call","function":{"name":obj["name"],"arguments":obj["arguments"]}}]

class PlanningAgent:
    def __init__(self,workspace:str|Path,logger:TestingLogger,client:Any,model:str,*,options:Mapping[str,Any]|None=None,
                 max_turns:int=MAX_TURNS,max_tools:int=MAX_TOOLS,request_timeout:float=MAX_REQUEST_SECONDS,
                 run_timeout:float=MAX_RUN_SECONDS,output_token_limit:int=MAX_OUTPUT_TOKENS):
        self.root=Path(workspace).resolve(strict=True); self.logger=logger; self.client=client; self.model=model
        self.options=dict(options or {"temperature":0.0,"num_ctx":16384,"num_predict":1200})
        self.max_turns=max_turns; self.max_tools=max_tools; self.request_timeout=request_timeout
        self.run_timeout=run_timeout; self.output_token_limit=output_token_limit
        self.started=time.monotonic(); self.tool_count=0; self.output_tokens=0; self.prompt_tokens=0; self.usage_known=True; self.prompt_usage_known=True; self.failed_tool_calls=0
        self.input_requests=set(); self.input_request_records=[]; self.failed_calls={}; self.finished=False
        self.messages=[
            {"role":"system","content":SYSTEM},
            {"role":"user","content":"Read task/TASK.md and supplied source-pack/. Any selected skill files are under skills/. Use the file tools, create the three deliverables, then finish."},
        ]

    def list_files(self,args:dict[str,Any])->dict[str,Any]:
        raw=args.get("path",".")
        target=self.root if raw in {"",".","./"} else safe_path(self.root,raw)
        if not target.is_dir(): raise ValueError("directory does not exist")
        files=[]
        for p in sorted(target.rglob("*")):
            if p.is_symlink(): raise ValueError("symlink in workspace")
            if p.is_file():
                files.append({"path":p.relative_to(self.root).as_posix(),"size_bytes":p.stat().st_size})
                if len(files)>100: return {"files":files[:100],"truncated":True}
        return {"files":files,"truncated":False}

    def read_file(self,args:dict[str,Any])->dict[str,Any]:
        p=safe_path(self.root,args.get("path"))
        if not p.is_file(): raise FileNotFoundError("file not found")
        raw=p.read_bytes()
        if len(raw)>MAX_READ: raise ValueError(f"file exceeds read limit {MAX_READ}")
        text=raw.decode("utf-8")
        ref=self.logger.capture_artifact("read-"+hashlib.sha256(str(p.relative_to(self.root)).encode()).hexdigest()[:12]+".txt",raw,"text/plain; charset=utf-8")
        self.logger.emit("agent_note","runner","planning","observed",{"note_type":"file_read","path":p.relative_to(self.root).as_posix(),"size_bytes":len(raw),"sha256":sha256_bytes(raw)},[ref])
        return {"path":p.relative_to(self.root).as_posix(),"content":text,"size_bytes":len(raw),"sha256":sha256_bytes(raw)}


    def write_file(self,args:dict[str,Any])->dict[str,Any]:
        rel=args.get("path"); data=args.get("content")
        if not isinstance(rel,str) or not rel.startswith("deliverables/"): raise ValueError("writes are permitted only beneath deliverables/")
        if not isinstance(data,str): raise ValueError("content must be text")
        raw=data.encode("utf-8")
        if len(raw)>MAX_WRITE: raise ValueError("file exceeds write size limit")
        p=safe_path(self.root,rel); dest=(self.root/"deliverables").resolve(strict=True)
        p.parent.mkdir(parents=True,exist_ok=True)
        p=safe_path(self.root,rel); p.parent.resolve(strict=True).relative_to(dest)
        tmp=p.with_name(p.name+".tmp-"+secrets.token_hex(4))
        with tmp.open("xb") as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
        self.logger.emit("file_changed","runner","planning","observed",{"path":p.relative_to(self.root).as_posix(),"action":"created_or_replaced","sha256":sha256_bytes(raw),"size_bytes":len(raw)})
        return {"status":"written","path":p.relative_to(self.root).as_posix(),"size_bytes":len(raw),"sha256":sha256_bytes(raw)}

    def dispatch(self,name:str,args:dict[str,Any])->dict[str,Any]:
        if name=="list_files": return self.list_files(args)
        if name=="read_file": return self.read_file(args)
        if name=="write_file": return self.write_file(args)
        if name=="request_input":
            q=args.get("question"); why=args.get("why_needed"); role=args.get("project_role")
            if not all(isinstance(v,str) and v.strip() and len(v)<=2000 for v in (q,why,role)):
                raise ValueError("question, why_needed and project_role must be non-empty text up to 2,000 chars")
            fingerprint=hashlib.sha256(" ".join((q+" "+why+" "+role).casefold().split()).encode()).hexdigest()
            repeated=fingerprint in self.input_requests
            self.input_request_records.append({"question":q,"why_needed":why,"project_role":role,"repeated":repeated})
            if repeated: raise RunnerError("repeated identical simulated input request")
            self.input_requests.add(fingerprint)
            return {"status":"captured_no_contact","response":None,"repeat":False,"instruction":"No human is available. Continue independently; record a genuinely unresolved decision and proceed with all independent work. No person was contacted."}
        if name=="finish":
            summary=args.get("summary"); known=args.get("known_limitations")
            if not isinstance(summary,str) or not summary.strip() or not isinstance(known,list) or any(not isinstance(x,str) for x in known):
                raise ValueError("finish requires summary text and known_limitations string array")
            result=validate_outputs(self.root)
            self.logger.capture_artifact("finish-summary.json",json.dumps({"summary":summary,"known_limitations":known},indent=2),"application/json")
            self.logger.emit("preflight_check","runner","verification","succeeded",{"check":"deliverable_structure","result":result})
            self.finished=True
            return {"finished":True,"validation":result}
        raise ValueError("unknown tool")

    def _tool(self,call:Mapping[str,Any])->dict[str,Any]:
        self.tool_count+=1; call_id=f"call-{self.tool_count:03d}"
        fn=call.get("function",{}); name=fn.get("name","unknown"); args=parse_args(fn.get("arguments",{}))
        if name not in ALLOWED:
            outcome={"error":"unknown_tool","message":"tool is not allowlisted"}
            self.logger.record_tool_call(str(name),call_id,args,outcome,status="failed",phase="planning")
            self.logger.emit("error","runner","planning","observed",{"kind":"unknown_tool_attempt","tool_name":str(name)})
            raise RunnerError("unknown tool attempted")
        try:
            outcome=self.dispatch(name,args); status="succeeded"
        except RunnerError as exc:
            self.logger.record_tool_call(name,call_id,args,{"error":"RunnerError","message":str(exc)},status="failed",phase="planning")
            reason="repeated_identical_input_request" if name=="request_input" else "runner_guard_stop"
            self.logger.emit("agent_loop_detected","runner","planning","failed",{"reason":reason,"tool_name":name,"tool_call_number":self.tool_count})
            raise
        except Exception as exc:
            outcome={"error":type(exc).__name__,"message":str(exc)[:1200]}; status="failed"
        self.logger.record_tool_call(name,call_id,args,outcome,status=status,phase="planning")
        if status=="failed":
            self.failed_tool_calls+=1
            fingerprint=sha256_bytes(canonical_json({"name":name,"arguments":args}))
            self.failed_calls[fingerprint]=self.failed_calls.get(fingerprint,0)+1
            if self.failed_calls[fingerprint]>=2:
                self.logger.emit("agent_loop_detected","runner","planning","failed",{"reason":"repeated_identical_failed_tool_call","tool_name":name,"tool_call_number":self.tool_count,"arguments_sha256":fingerprint})
                raise RunnerError("repeated identical failed tool call")
        return {"name":name,"outcome":outcome,"status":status}


    def run(self)->dict[str,Any]:
        reason="agent did not finish"; status="failed"; turn=0
        no_tool_fp=None; same_no_tool=0; consecutive_no_tool=0
        for turn in range(1,self.max_turns+1):
            if time.monotonic()-self.started>=self.run_timeout:
                reason="run wall-clock limit reached"; break
            if self.tool_count>=self.max_tools:
                reason="tool-call limit reached"; break
            opts=dict(self.options)
            if self.usage_known and "num_predict" in opts:
                remaining=self.output_token_limit-self.output_tokens
                if remaining<=0: reason="generated-token limit reached"; break
                opts["num_predict"]=min(int(opts["num_predict"]),remaining)
            body={"model":self.model,"messages":self.messages,"tools":TOOLS,"stream":False,"options":opts,"think":False}
            raw=json.dumps(body,ensure_ascii=False,sort_keys=True); req=f"{self.logger.run_id}-turn-{turn:03d}"
            ref=self.logger.capture_artifact(f"model-request-{turn:03d}.json",raw,"application/json")
            self.logger.emit("model_request_started","runner","planning","started",{"request_id":req,"turn":turn,"timeout_seconds":self.request_timeout,"model_id":self.model,"request_sha256":sha256_bytes(raw.encode())},[ref])
            began=time.monotonic()
            try:
                if hasattr(self.client,"timeout"): self.client.timeout=self.request_timeout
                response=self.client.chat(body)
            except Exception as exc:
                latency=round((time.monotonic()-began)*1000,3)
                self.logger.emit("model_request_failed","runtime","planning","failed",{"request_id":req,"turn":turn,"elapsed_ms":latency,"error_type":type(exc).__name__,"message":str(exc)[:1000]})
                reason=f"model request failed: {type(exc).__name__}"; break
            latency=round((time.monotonic()-began)*1000,3)
            self.logger.emit("model_request_succeeded","runtime","planning","succeeded",{"request_id":req,"turn":turn,"elapsed_ms":latency})
            message=response.get("message",{})
            safe={k:v for k,v in message.items() if k not in {"thinking","reasoning","analysis"}}
            safe_response={k:v for k,v in response.items() if k not in {"thinking","reasoning","analysis"}}
            safe_response["message"]=safe
            prompt_tokens=response.get("prompt_eval_count"); completion_tokens=response.get("eval_count")
            usage={"prompt_tokens":prompt_tokens if isinstance(prompt_tokens,int) else None,
                   "completion_tokens":completion_tokens if isinstance(completion_tokens,int) else None}
            if isinstance(prompt_tokens,int) and prompt_tokens>=0: self.prompt_tokens+=prompt_tokens
            else: self.prompt_usage_known=False
            if isinstance(completion_tokens,int) and completion_tokens>=0: self.output_tokens+=completion_tokens
            else: self.usage_known=False
            self.logger.record_model_exchange({"provider":"ollama-local","model_id":self.model,"request_id":req,"latency_ms":latency,"finish_reason":response.get("done_reason")},
                raw,json.dumps(safe_response,ensure_ascii=False,sort_keys=True),usage,phase="planning")
            if self.usage_known and self.output_tokens>self.output_token_limit:
                reason="generated-token limit exceeded"; break
            calls=safe.get("tool_calls") if isinstance(safe.get("tool_calls"),list) else []
            if not calls: calls=parse_text_call(safe.get("content"))
            if not calls:
                content=str(safe.get("content") or ""); fp=hashlib.sha256(" ".join(content.split()).encode()).hexdigest()
                same_no_tool=same_no_tool+1 if fp==no_tool_fp else 1; no_tool_fp=fp; consecutive_no_tool+=1
                self.messages.append({"role":"assistant","content":content})
                if same_no_tool>=2 or consecutive_no_tool>=4:
                    reason="repeated no-tool response loop"
                    self.logger.emit("agent_loop_detected","runner","planning","failed",{"reason":"repeated_no_tool_response","turn":turn,"identical_count":same_no_tool,"consecutive_count":consecutive_no_tool})
                    break
                self.messages.append({"role":"user","content":"Continue using one available tool. Do not repeat the previous response. Inspect, write a required deliverable, record a genuine simulated input request, or finish if all outputs are valid."})
                continue
            no_tool_fp=None; same_no_tool=0; consecutive_no_tool=0
            assistant={"role":"assistant","content":safe.get("content") or ""}
            if safe.get("tool_calls"): assistant["tool_calls"]=safe["tool_calls"]
            self.messages.append(assistant)
            for call in calls:
                if self.tool_count>=self.max_tools:
                    reason="tool-call limit reached"
                    break
                try: result=self._tool(call)
                except RunnerError as exc: reason=str(exc); break
                self.messages.append({"role":"tool","tool_name":result["name"],"content":json.dumps(result["outcome"],ensure_ascii=False)})
                if result["name"]=="finish" and result["status"]=="succeeded" and result["outcome"].get("finished"):
                    self.finished=True; status="succeeded"; reason="three deliverables validated"; break
            if self.finished or status=="succeeded" or reason!="agent did not finish": break
        metrics={"status":status,"stop_reason":reason,"turns":turn,"tool_calls":self.tool_count,
                 "failed_tool_calls":self.failed_tool_calls,
                 "prompt_tokens":self.prompt_tokens if self.prompt_usage_known else None,
                 "completion_tokens":self.output_tokens if self.usage_known else None,
                 "simulated_input_requests":len(self.input_request_records),
                 "unique_simulated_input_requests":len(self.input_requests),
                 "repeated_simulated_input_requests":sum(1 for x in self.input_request_records if x["repeated"]),
                 "input_request_records":self.input_request_records,
                 "output_tokens":self.output_tokens if self.usage_known else None,
                 "token_usage_available":self.usage_known,"elapsed_seconds":round(time.monotonic()-self.started,3)}
        self.logger.emit("agent_note","runner","delivery","observed",{"note_type":"run_metrics",**metrics})
        return metrics



def save_private(path:Path,data:Mapping[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(dict(data),f,ensure_ascii=False,indent=2,sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
    try: path.chmod(0o600)
    except OSError: pass

def make_score_packet(label:str,workspace:Path,metrics:Mapping[str,Any],validation:Mapping[str,Any]|None,target:Path)->dict[str,Any]:
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
        for name in REQUIRED:
            p=workspace/"deliverables"/name
            if p.is_file(): z.write(p,f"deliverables/{name}")
        trace={"blind_label":label,"metrics":dict(metrics),"deliverables":dict(validation or {"status":"NOT_COMPLETE"}),
               "raw_prompts_included":False,"skill_text_included":False,"condition_key_included":False}
        z.writestr("observable-run-summary.json",json.dumps(trace,indent=2,sort_keys=True))
    return {"path":str(target),"size_bytes":target.stat().st_size,"sha256":sha256_file(target)}

def run_block(*,output_dir:str|Path,key_file:str|Path,task_dir:str|Path=DEFAULT_TASK,
              mp_source:str|Path,ct_source:str|Path,model:str,base_url:str="http://127.0.0.1:11434",
              client:Any|None=None,max_turns:int=MAX_TURNS,max_tools:int=MAX_TOOLS,
              request_timeout:float=MAX_REQUEST_SECONDS,run_timeout:float=MAX_RUN_SECONDS,
              output_token_limit:int=MAX_OUTPUT_TOKENS)->dict[str,Any]:
    output=Path(output_dir).expanduser().resolve(); key=Path(key_file).expanduser().resolve()
    if output==key or output in key.parents: raise ValueError("private condition key must be outside run output")
    if output.exists() and any(output.iterdir()): raise FileExistsError("output directory must be new or empty")
    if key.exists(): raise FileExistsError("private condition key already exists")
    if not model: raise ValueError("exact model name required")
    model_client=client or OllamaClient(base_url,timeout=request_timeout)
    version=model_client.info(); models=model_client.list_models()
    matches=[m for m in models if (m.get("name") or m.get("model"))==model]
    if len(matches)!=1: raise ValueError("requested model is not installed under the exact name")
    model_record={"provider":"ollama-local","name":model,"digest":matches[0].get("digest"),"ollama_version":version.get("version","unknown")}
    mp_info=verify_source(mp_source,MP_COMMIT,MP_FILES); ct_info=verify_source(ct_source,CT_COMMIT,CT_FILES)
    randomisation_seed=secrets.token_hex(16); rng=random.Random(randomisation_seed)
    labels=["A","B","C","D"]; rng.shuffle(labels)
    cells=["MP0_CT0","MP1_CT0","MP0_CT1","MP1_CT1"]; rng.shuffle(cells)
    mapping=dict(zip(labels,cells)); reverse={v:k for k,v in mapping.items()}
    task=Path(task_dir).resolve(strict=True); task_pin=verify_task_fixture(task); task_hash=tree_sha(task)
    output.mkdir(parents=True,exist_ok=True); output.chmod(0o700)
    runs=output/"runs"; workspaces=output/"workspaces"; packets=output/"score-packets"
    for d in (runs,workspaces,packets): d.mkdir(mode=0o700); d.chmod(0o700)
    save_private(key,{"experiment_id":"qbatch-checklist-elaboration-v1","created_at_utc":utc_now(),
        "blind_label_to_cell_id":mapping,"execution_order":cells,"randomisation_seed":randomisation_seed,"randomisation_method":"Python random.Random seeded from private 128-bit secret","task_sha256":task_hash,
        "mp_source":mp_info,"ct_source":ct_info,"task_fixture_pin":task_pin,"model":model_record,
        "warning":"PRIVATE CONDITION KEY: withhold until blind scores are frozen."})
    report={}
    for cell in cells:
        label=reverse[cell]; mp_on=cell.startswith("MP1"); ct_on=cell.endswith("CT1")
        workspace=workspaces/label; run_dir=runs/("run-"+label.lower())
        prepared=prepare_workspace(task,workspace,mp_source=mp_source,ct_source=ct_source,mp_enabled=mp_on,ct_enabled=ct_on)
        condition={"mp_enabled":mp_on,"ct_enabled":ct_on,"task_sha256":prepared["task_sha256"],
                   "visible_inputs_sha256":prepared["visible_inputs_sha256"],"skills":prepared["skills"]}
        config_sha=sha256_bytes(canonical_json(condition)); run_id="checklist-"+secrets.token_hex(8)
        revision="unknown"
        try: revision=git(PACKAGE_DIR.parents[1],"rev-parse","HEAD")
        except Exception: pass
        manifest={
            "run_id":run_id,"condition_label":label,"task_brief_sha256":task_hash,"condition_config_sha256":config_sha,
            "logger_version":LOGGER_VERSION,"schema_version":SCHEMA_VERSION,"started_at_utc":utc_now(),
            "model":model_record,"environment":{"python":platform.python_version(),"platform":platform.platform(),"runner_commit":revision},
            "resource_limits":{"max_turns":max_turns,"max_tool_calls":max_tools,"max_request_seconds":request_timeout,
                               "max_run_seconds":run_timeout,"max_output_tokens":output_token_limit},
            "base_commit":revision,"cell_id_private":cell,"skill_source_private":prepared["skills"],
        }
        logger=TestingLogger(run_dir,workspace,manifest)
        agent=PlanningAgent(workspace,logger,model_client,model,options={"temperature":0.0,"num_ctx":16384,"num_predict":1200},
            max_turns=max_turns,max_tools=max_tools,request_timeout=request_timeout,
            run_timeout=run_timeout,output_token_limit=output_token_limit)
        try:
            metrics=agent.run()
            validation=validate_outputs(workspace) if metrics["status"]=="succeeded" else None
            logger.emit("preflight_check","runner","verification","succeeded" if validation else "failed",
                        {"check":"final_deliverables","result":validation or {"status":"NOT_COMPLETE"}})
            logger.finish("succeeded" if validation else "failed",metrics["stop_reason"])
        except Exception as exc:
            metrics={"status":"failed","stop_reason":f"{type(exc).__name__}: {str(exc)[:1000]}","turns":0,
                     "tool_calls":agent.tool_count,"simulated_input_requests":len(agent.input_request_records),"unique_simulated_input_requests":len(agent.input_requests), "input_request_records":agent.input_request_records,
                     "elapsed_seconds":round(time.monotonic()-agent.started,3)}
            validation=None
            logger.emit("error","runner","delivery","observed",{"kind":"runner_exception","message":metrics["stop_reason"]})
            logger.finish("failed",metrics["stop_reason"])
        finally:
            logger.close()
        try: log_check=validate_run(run_dir)
        except (LogValidationError,OSError) as exc: log_check={"status":"FAIL","error":str(exc)}
        packet=make_score_packet(label,workspace,metrics,validation,packets/f"score-{label}.zip")
        report[label]={"metrics":metrics,"deliverables":validation or {"status":"NOT_COMPLETE"},
                       "log_validation":log_check,"score_packet":packet}
    block={"report_version":"1.0","experiment_id":"qbatch-checklist-elaboration-v1","created_at_utc":utc_now(),
           "status":"FEASIBILITY_BLOCK_COMPLETE","model":model_record,"task_sha256":task_hash,"runs":report,
           "interpretation":"One run per factorial cell is a feasibility block only, not evidence of efficacy. Condition mapping is in a separate private key."}
    (output/"blinded-block-report.json").write_text(json.dumps(block,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return block



def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    doctor=sub.add_parser("doctor"); doctor.add_argument("--base-url",default="http://127.0.0.1:11434")
    run=sub.add_parser("run-block")
    run.add_argument("--output",required=True)
    run.add_argument("--key-file",required=True)
    run.add_argument("--task-dir",default=str(DEFAULT_TASK))
    run.add_argument("--mp-source",required=True)
    run.add_argument("--ct-source",required=True)
    run.add_argument("--model",required=True)
    run.add_argument("--base-url",default="http://127.0.0.1:11434")
    args=parser.parse_args()
    try:
        if args.command=="doctor":
            client=OllamaClient(args.base_url)
            info=client.info(); models=client.list_models()
            result={"status":"PASS","ollama_version":info.get("version","unknown"),
                    "models":[m.get("name") or m.get("model") for m in models],"note":"No prompt was sent."}
        else:
            result=run_block(output_dir=args.output,key_file=args.key_file,task_dir=args.task_dir,
                mp_source=args.mp_source,ct_source=args.ct_source,model=args.model,base_url=args.base_url)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result.get("status") in {"PASS","FEASIBILITY_BLOCK_COMPLETE"} else 1
    except Exception as exc:
        print(json.dumps({"status":"FAIL","error":f"{type(exc).__name__}: {exc}"},indent=2))
        return 1

if __name__=="__main__":
    raise SystemExit(main())
