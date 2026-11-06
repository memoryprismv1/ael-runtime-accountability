"""Planning-only checklist-elaboration runner."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
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
        self.started=time.monotonic(); self.tool_count=0; self.output_tokens=0; self.usage_known=True
        self.input_requests=set(); self.finished=False
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
            if fingerprint in self.input_requests: raise RunnerError("repeated identical simulated input request")
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
        if name not in ALLOWED: raise ValueError("tool is not allowlisted")
        try:
            outcome=self.dispatch(name,args); status="succeeded"
        except RunnerError:
            self.logger.record_tool_call(name,call_id,args,{"error":"RunnerError","message":"repeated input request"},status="failed",phase="planning")
            raise
        except Exception as exc:
            outcome={"error":type(exc).__name__,"message":str(exc)[:1200]}; status="failed"
        self.logger.record_tool_call(name,call_id,args,outcome,status=status,phase="planning")
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
                try: result=self._tool(call)
                except RunnerError as exc: reason=str(exc); break
                self.messages.append({"role":"tool","tool_name":result["name"],"content":json.dumps(result["outcome"],ensure_ascii=False)})
                if result["name"]=="finish" and result["status"]=="succeeded" and result["outcome"].get("finished"):
                    self.finished=True; status="succeeded"; reason="three deliverables validated"; break
            if self.finished or status=="succeeded" or reason!="agent did not finish": break
        metrics={"status":status,"stop_reason":reason,"turns":turn,"tool_calls":self.tool_count,
                 "simulated_input_requests":len(self.input_requests),
                 "output_tokens":self.output_tokens if self.usage_known else None,
                 "token_usage_available":self.usage_known,"elapsed_seconds":round(time.monotonic()-self.started,3)}
        self.logger.emit("agent_note","runner","delivery","observed",{"note_type":"run_metrics",**metrics})
        return metrics

