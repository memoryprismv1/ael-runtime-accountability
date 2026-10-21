"""Paired local-Ollama controller for the CT A/B software task.

Run folders contain blind labels A/B. The skill-condition mapping is written
to a separate controller-private sidecar outside the run output and must not
be handed to blind assessors until scoring is frozen.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import secrets
import shutil
import sys
import tempfile
import time
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from .acceptance import run_acceptance
from .agent_loop import AgentLoop, OllamaClient, RunnerError
from .logger import LOGGER_VERSION, SCHEMA_VERSION, RunLogger, sha256_bytes, utc_now
from .validate_log import LogValidationError, validate_pair, validate_run

PACKAGE_DIR = Path(__file__).resolve().parent
TASK_DIR = PACKAGE_DIR / "client_task"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_text(text: str) -> str:
    return _sha_bytes(text.encode("utf-8"))


def _folder_sha(root: Path) -> str:
    h = hashlib.sha256()
    ignored = {".git", "__pycache__", ".venv", "venv", "node_modules"}
    for path in sorted(p for p in root.rglob("*") if p.is_file() and not any(part in ignored for part in p.relative_to(root).parts)):
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        content = path.read_bytes()
        h.update(len(content).to_bytes(8, "big"))
        h.update(content)
    return h.hexdigest()


def _starter_sha(starter: str) -> str:
    rel = b"STARTER.md"
    content = starter.encode("utf-8")
    h = hashlib.sha256()
    h.update(len(rel).to_bytes(4, "big"))
    h.update(rel)
    h.update(len(content).to_bytes(8, "big"))
    h.update(content)
    return h.hexdigest()


def _environment(model_info: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "ollama_version": str(model_info.get("version", "unknown")),
        "transport": "http://127.0.0.1 loopback only"
    }


def _zip_workspace(workspace: Path) -> bytes:
    import io
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in workspace.rglob("*") if p.is_file()):
            if any(part in {".git", "__pycache__", ".venv", "venv"} for part in path.relative_to(workspace).parts):
                continue
            archive.write(path, path.relative_to(workspace).as_posix())
    return buffer.getvalue()


def _safe_key_path(output: Path, key_path: str | Path | None) -> Path:
    if key_path is None:
        candidate = output.parent / ("." + output.name + "-controller-private") / "condition-key.json"
    else:
        candidate = Path(key_path).expanduser().resolve()
    # This key must not be within the run output, where it could be bundled
    # with blinded logs or scoring packets.
    resolved_parent = candidate.parent.resolve()
    resolved_candidate = resolved_parent / candidate.name
    if resolved_candidate == output or output in resolved_candidate.parents:
        raise ValueError("condition-key path must be outside the experiment output directory")
    return resolved_candidate


def _ensure_separate_key(output: Path, key_path: Path) -> None:
    if key_path.exists():
        raise FileExistsError(f"controller-private key file already exists: {key_path}")
    key_path.parent.mkdir(parents=True, exist_ok=True)


def _base_files() -> tuple[str, str, str, str]:
    brief_path = TASK_DIR / "CLIENT_BRIEF.md"
    contract_path = TASK_DIR / "API_CONTRACT.json"
    starter_path = TASK_DIR / "STARTER.md"
    if not all(p.is_file() for p in (brief_path, contract_path, starter_path)):
        raise FileNotFoundError("frozen client task files are missing")
    brief = brief_path.read_text(encoding="utf-8")
    contract = contract_path.read_text(encoding="utf-8")
    contract_doc = json.loads(contract)
    if contract_doc.get("contract_version") != "1.0":
        raise ValueError("unsupported task API contract version")
    starter = starter_path.read_text(encoding="utf-8")
    bundle_hash = _sha_text(brief + "\0" + contract + "\0" + starter)
    return brief, contract, starter, bundle_hash


def _new_manifest(run_id: str, label: str, task_hash: str, config_hash: str, model: str,
                  model_info: Mapping[str, Any], limits: Mapping[str, Any], starter_hash: str) -> dict[str, Any]:
    return {
        "run_id":run_id,
        "condition_label":label,
        "task_brief_sha256":task_hash,
        "condition_config_sha256":config_hash,
        "logger_version":LOGGER_VERSION,
        "schema_version":SCHEMA_VERSION,
        "started_at_utc":utc_now(),
        "model":{"provider":"ollama-local","model_id":model,"version":str(model_info.get("version","unknown"))},
        "environment":_environment(model_info),
        "resource_limits":dict(limits),
        "base_commit":"starter-sha256:"+starter_hash
    }


def _condition_config(enabled: bool, model: str, options: Mapping[str, Any], skill_hash: str | None, max_turns: int, max_tool_calls: int) -> tuple[str, str]:
    value = {
        "model":model,
        "skill_enabled":enabled,
        "skill_sha256":skill_hash if enabled else None,
        "options":dict(options),
        "max_turns":max_turns,
        "max_tool_calls":max_tool_calls,
        "tool_version":"0.1.0",
        "schema_version":SCHEMA_VERSION
    }
    return _sha_text(json.dumps(value,sort_keys=True,separators=(",",":"))), json.dumps(value,sort_keys=True)


def _run_one(label: str, enabled: bool, workspace: Path, run_dir: Path, acceptance_dir: Path,
             model: str, model_info: Mapping[str, Any], client: OllamaClient, brief: str, contract: str,
             skill_text: str | None, skill_hash: str | None, task_hash: str, starter_hash: str,
             options: Mapping[str, Any], limits: Mapping[str, Any], max_turns: int, max_tool_calls: int, pair_id: str) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "STARTER.md").write_text((TASK_DIR / "STARTER.md").read_text(encoding="utf-8"), encoding="utf-8")
    # Re-hash the common starting tree. A/B must begin with the same bytes.
    start_hash = _folder_sha(workspace)
    if start_hash != starter_hash:
        raise ValueError("starter workspace hash does not match frozen baseline")
    run_id = f"{pair_id}-{label.lower()}"
    config_hash, _ = _condition_config(enabled, model, options, skill_hash, max_turns, max_tool_calls)
    manifest = _new_manifest(run_id,label,task_hash,config_hash,model,model_info,limits,starter_hash)
    manifest.update({
        "client_brief_sha256":_sha_bytes((TASK_DIR/"CLIENT_BRIEF.md").read_bytes()),
        "api_contract_sha256":_sha_bytes((TASK_DIR/"API_CONTRACT.json").read_bytes()),
        "starter_sha256":starter_hash,
        "acceptance_suite_sha256":_sha_bytes((PACKAGE_DIR/"acceptance.py").read_bytes()),
        "acceptance_contract_version":"1.0"
    })
    logger = RunLogger(run_dir,workspace,manifest)
    result: dict[str, Any] = {
        "condition_label":label,
        "run_id":run_id,
        "agent_status":"not_started",
        "acceptance_status":"not_run",
        "acceptance_score":None,
        "errors":[]
    }
    try:
        loop = AgentLoop(
            workspace, logger, client, model, brief, contract,
            skill_text if enabled else None, config_hash, options,
            max_turns=max_turns,max_tool_calls=max_tool_calls
        )
        agent_result=loop.run()
        result["agent_status"]=agent_result["status"]
        result["agent_turns"]=agent_result["turns"]
        result["agent_tool_calls"]=agent_result["tool_calls"]
        result["summary"]=(agent_result.get("finish") or {}).get("summary","")
        result["known_issues"]=(agent_result.get("finish") or {}).get("known_issues",[])
    except Exception as exc:
        result["agent_status"]="failed"
        result["errors"].append(f"{type(exc).__name__}: {str(exc)[:2000]}")
        logger.emit("error","runner","implementation","observed",{"kind":"agent_run_failed","error_type":type(exc).__name__,"message":str(exc)[:2000]})
    # Archive the submitted source tree separately from the live workspace so
    # assessors can inspect exactly what was judged.
    try:
        bundle_ref=logger.capture_artifact("application-source.zip",_zip_workspace(workspace),"application/zip")
        logger.emit("artifact_captured","runner","delivery","observed",{"artifact_role":"final_application_source","workspace_sha256":_folder_sha(workspace)},[bundle_ref])
    except Exception as exc:
        result["errors"].append(f"source bundle capture failed: {type(exc).__name__}: {exc}")
    if result["agent_status"]=="finished":
        try:
            acceptance_dir.mkdir(parents=True,exist_ok=False)
            accepted=run_acceptance(workspace,acceptance_dir)
            report_ref=logger.capture_artifact("acceptance-report.json",(acceptance_dir/"acceptance-report.json").read_bytes(),"application/json")
            for log_path in acceptance_dir.glob("application-*.log"):
                logger.capture_artifact(log_path.name,log_path.read_bytes(),"text/plain")
            logger.record_test_result(["independent_acceptance_suite"],0 if accepted["status"]=="PASS" else 1,accepted["passed"],accepted["failed"],[report_ref])
            result["acceptance_status"]=accepted["status"]
            result["acceptance_score"]={"passed":accepted["passed"],"failed":accepted["failed"],"total":accepted["total"]}
            result["acceptance_checks"]=accepted["checks"]
        except Exception as exc:
            result["acceptance_status"]="ERROR"
            result["errors"].append(f"acceptance runner failed: {type(exc).__name__}: {str(exc)[:2000]}")
            logger.emit("error","runner","verification","observed",{"kind":"acceptance_runner_error","error_type":type(exc).__name__,"message":str(exc)[:2000]})
    else:
        logger.record_test_result(["independent_acceptance_suite"],1,None,None,[])
        result["acceptance_status"]="NOT_RUN_AGENT_FAILED"
    run_status="succeeded" if result["agent_status"]=="finished" and result["acceptance_status"]=="PASS" else "failed"
    result["source_tree_sha256"]=_folder_sha(workspace)
    result["source_file_count"]=sum(p.is_file() for p in workspace.rglob("*"))
    result["completed_at_utc"]=utc_now()
    logger.capture_artifact("blind-run-result.json",json.dumps(result,ensure_ascii=False,indent=2),"application/json")
    logger.finish(run_status,"A/B build run complete; independent acceptance scored after agent finished. No efficacy conclusion is implied.")
    try:
        result["log_validation"]=validate_run(run_dir)
    except Exception as exc:
        result["log_validation"]={"status":"FAIL","error":f"{type(exc).__name__}: {exc}"}
        result["errors"].append("log validation failed: "+str(exc))
    return result


def run_pair(output_dir: str | Path, model: str, skill_file: str | Path, base_url: str = "http://127.0.0.1:11434",
             temperature: float = 0.0, num_ctx: int = 8192, num_predict: int = 1800,
             timeout: float = 180.0, max_turns: int = 36, max_tool_calls: int = 100,
             key_file: str | Path | None = None, client: OllamaClient | None = None,
             allow_host_execution: bool = False) -> dict[str, Any]:
    """Run one locally hosted model twice with identical controls, changing only skill inclusion."""
    if not allow_host_execution:
        raise PermissionError("The post-run acceptance suite executes model-generated app.py as this OS user; there is no OS sandbox. Run inside a disposable VM/container and pass allow_host_execution=True only after isolating secrets and valuable files.")
    output = Path(output_dir).expanduser().resolve()
    key_path = _safe_key_path(output,key_file)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory must be new or empty: {output}")
    if key_path.exists():
        raise FileExistsError(f"controller-private key already exists: {key_path}")
    if not model or not isinstance(model,str):
        raise ValueError("an exact installed local Ollama model name is required")
    skill_path=Path(skill_file).expanduser().resolve(strict=True)
    if not skill_path.is_file():
        raise ValueError("skill_file must be a file")
    skill_bytes=skill_path.read_bytes()
    skill_text=skill_bytes.decode("utf-8")
    if not skill_text.strip():
        raise ValueError("Critical Thinking skill file is empty")
    skill_hash=_sha_bytes(skill_bytes)
    # Validate the local model and frozen task before creating output directories or the private key.
    ollama=client or OllamaClient(base_url,timeout=timeout)
    model_info=ollama.info()
    available=ollama.list_models()
    names={str(m.get("name") or m.get("model") or "") for m in available}
    if model not in names:
        raise ValueError(f"model {model!r} is not installed under that exact name; available: {sorted(n for n in names if n)}")
    brief,contract,starter,task_hash=_base_files()
    starter_hash=_starter_sha(starter)
    opts={"temperature":temperature,"num_ctx":num_ctx,"num_predict":num_predict}
    limits={"timeout_seconds_per_model_request":timeout,"max_turns":max_turns,"max_tool_calls":max_tool_calls,"options":opts,"tool_version":"0.1.0"}
    _ensure_separate_key(output,key_path)
    output.mkdir(parents=True,exist_ok=True)
    runs_dir=output/"runs"
    workspaces_dir=output/"workspaces"
    acceptance_dir=output/"acceptance"
    for p in (runs_dir,workspaces_dir,acceptance_dir):
        p.mkdir()
    labels=["A","B"]
    labels.reverse() if secrets.randbelow(2) else None
    enabled_label=labels[secrets.randbelow(2)]
    enabled_by_label={enabled_label:True,("B" if enabled_label=="A" else "A"):False}
    pair_id="ctab-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+secrets.token_hex(3)
    # Keep the key separate from all output artifacts; do not upload or send it to assessors.
    key_doc={
        "pair_id":pair_id,
        "created_at_utc":utc_now(),
        "condition_mapping":{label:("skill_enabled" if enabled else "skill_disabled") for label,enabled in enabled_by_label.items()},
        "skill_file_basename":skill_path.name,
        "skill_file_sha256":skill_hash,
        "task_bundle_sha256":task_hash,
        "model":model,
        "options":opts,
        "note":"Controller-private. Keep separate from blind scoring packets until assessor scores are frozen."
    }
    key_path.write_text(json.dumps(key_doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (output/"task-manifest.json").write_text(json.dumps({"pair_id":pair_id,"task_bundle_sha256":task_hash,"client_brief_sha256":_sha_text(brief),"api_contract_sha256":_sha_text(contract),"starter_sha256":starter_hash,"acceptance_suite_sha256":_sha_bytes((PACKAGE_DIR/"acceptance.py").read_bytes()),"acceptance_contract_version":"1.0","model":model,"common_options":opts,"base_commit":"starter-sha256:"+starter_hash},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    labels_to_run=list(labels)
    # execution order is randomized separately from the A/B condition mapping.
    if secrets.randbelow(2):
        labels_to_run.reverse()
    results={}
    for label in labels_to_run:
        enabled=enabled_by_label[label]
        workspace=workspaces_dir/label
        run_dir=runs_dir/("run-"+label.lower())
        accepted_dir=acceptance_dir/label
        result=_run_one(label,enabled,workspace,run_dir,accepted_dir,model,model_info,ollama,brief,contract,skill_text,skill_hash,task_hash,starter_hash,opts,limits,max_turns,max_tool_calls,pair_id)
        results[label]=result
    pair_validation: dict[str,Any]
    try:
        pair_validation=validate_pair(runs_dir/"run-a",runs_dir/"run-b")
        pair_validation["status"]="PASS"
    except Exception as exc:
        pair_validation={"status":"FAIL","error":f"{type(exc).__name__}: {exc}"}
    all_ok=pair_validation["status"]=="PASS" and all(r["agent_status"]=="finished" and r["acceptance_status"]!="ERROR" and r["log_validation"].get("status")!="FAIL" for r in results.values())
    blinded_report={
        "report_version":"1.0",
        "pair_id":pair_id,
        "created_at_utc":utc_now(),
        "status":"RUNS_COMPLETE" if all(r["agent_status"]=="finished" for r in results.values()) else "RUN_INCOMPLETE",
        "acceptance_results":{label:{"status":r["acceptance_status"],"score":r["acceptance_score"],"checks":r.get("acceptance_checks",[])} for label,r in sorted(results.items())},
        "per_run":{"A":{k:v for k,v in results["A"].items() if k not in {"known_issues"}}, "B":{k:v for k,v in results["B"].items() if k not in {"known_issues"}}},
        "pair_log_validation":pair_validation,
        "interpretation":"One paired pilot is descriptive. Acceptance scores test this implementation against the frozen client contract; they do not independently establish general reasoning improvement. Score application artifacts blind to A/B condition; open the private condition key only after scores are frozen."
    }
    (output/"blinded-pair-report.json").write_text(json.dumps(blinded_report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return blinded_report


def _doctor(base_url: str) -> dict[str,Any]:
    client=OllamaClient(base_url)
    info=client.info()
    models=client.list_models()
    return {"status":"PASS","ollama_version":info.get("version","unknown"),"models":[m.get("name") or m.get("model") for m in models],"base_url":base_url,"note":"Connectivity/model inventory only; no prompt was sent."}


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    d=sub.add_parser("doctor",help="Check a loopback Ollama server and list local models.")
    d.add_argument("--base-url",default="http://127.0.0.1:11434")
    r=sub.add_parser("run-pair",help="Run a blinded skill-off/skill-on pair and independently score both applications.")
    r.add_argument("--output",required=True,help="New output directory. Workspaces, logs and blinded results are placed here.")
    r.add_argument("--model",required=True,help="Exact model name from ollama list.")
    r.add_argument("--ct-skill",required=True,help="Path to the exact Critical Thinking skill file, outside the experiment output.")
    r.add_argument("--base-url",default="http://127.0.0.1:11434")
    r.add_argument("--key-file",help="Optional controller-private key path, which MUST remain outside --output.")
    r.add_argument("--temperature",type=float,default=0.0)
    r.add_argument("--num-ctx",type=int,default=8192)
    r.add_argument("--num-predict",type=int,default=1800)
    r.add_argument("--timeout",type=float,default=180.0)
    r.add_argument("--max-turns",type=int,default=36)
    r.add_argument("--max-tool-calls",type=int,default=100)
    r.add_argument("--allow-host-execution",action="store_true",help="REQUIRED: acknowledge that model-generated app.py is executed as this OS user without an OS sandbox. Use only inside a disposable VM/container without secrets or valuable files.")
    args=parser.parse_args()
    try:
        if args.command=="doctor":
            result=_doctor(args.base_url)
        else:
            result=run_pair(args.output,args.model,args.ct_skill,args.base_url,args.temperature,args.num_ctx,args.num_predict,args.timeout,args.max_turns,args.max_tool_calls,args.key_file,allow_host_execution=args.allow_host_execution)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result.get("status")=="PASS" or result.get("status")=="RUNS_COMPLETE" else 1
    except Exception as exc:
        print(json.dumps({"status":"FAIL","error":f"{type(exc).__name__}: {exc}"},indent=2))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
