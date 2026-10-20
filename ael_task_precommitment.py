#!/usr/bin/env python3
"""AEL task-level precommitment and audit records. Standard library only."""
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SKILL_PATH = ROOT / "dependencies" / "critical-thinking" / "SKILL.md"
DEPENDENCY_PATH = ROOT / "dependencies" / "critical-thinking" / "DEPENDENCY.json"

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS task_runs (
 task_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, chat_id TEXT NOT NULL,
 request TEXT NOT NULL, state TEXT NOT NULL, model_name TEXT, skill_commit TEXT NOT NULL, skill_blob_sha TEXT NOT NULL,
 current_case_artifact_id TEXT, current_plan_artifact_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(task_id,account_id,project_id,chat_id)
);
CREATE TABLE IF NOT EXISTS task_artifacts (
 artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, chat_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('case_notes','implementation_plan','verification_report')), version INTEGER NOT NULL,
 content TEXT NOT NULL, content_sha256 TEXT NOT NULL, based_on_case_sha256 TEXT, dependency_commit TEXT NOT NULL,
 dependency_blob_sha TEXT NOT NULL, created_at TEXT NOT NULL, creator TEXT NOT NULL CHECK(creator IN ('assistant','user','system')),
 metadata_json TEXT NOT NULL DEFAULT '{}',
 UNIQUE(task_id,account_id,project_id,chat_id,kind,version)
);
CREATE TRIGGER IF NOT EXISTS task_artifacts_no_update BEFORE UPDATE ON task_artifacts BEGIN SELECT RAISE(ABORT,'task artifacts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS task_artifacts_no_delete BEFORE DELETE ON task_artifacts BEGIN SELECT RAISE(ABORT,'task artifacts are retained'); END;
CREATE TABLE IF NOT EXISTS task_decisions (
 decision_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, chat_id TEXT NOT NULL,
 decision_type TEXT NOT NULL CHECK(decision_type IN ('case_notes','implementation_plan')), artifact_id TEXT NOT NULL,
 artifact_sha256 TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('approve','reject')),
 actor TEXT NOT NULL CHECK(actor IN ('user','delegated_human','system')), note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
 FOREIGN KEY(artifact_id) REFERENCES task_artifacts(artifact_id)
);
CREATE TRIGGER IF NOT EXISTS task_decisions_no_update BEFORE UPDATE ON task_decisions BEGIN SELECT RAISE(ABORT,'task decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS task_decisions_no_delete BEFORE DELETE ON task_decisions BEGIN SELECT RAISE(ABORT,'task decisions are retained'); END;
CREATE TABLE IF NOT EXISTS task_events (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, task_id TEXT NOT NULL,
 account_id TEXT NOT NULL, project_id TEXT NOT NULL, chat_id TEXT NOT NULL, event_type TEXT NOT NULL,
 actor TEXT NOT NULL CHECK(actor IN ('user','assistant','system','external')), from_state TEXT, to_state TEXT NOT NULL,
 artifact_id TEXT, artifact_sha256 TEXT, note TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS task_events_no_update BEFORE UPDATE ON task_events BEGIN SELECT RAISE(ABORT,'task event history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS task_events_no_delete BEFORE DELETE ON task_events BEGIN SELECT RAISE(ABORT,'task event history is retained'); END;
CREATE TABLE IF NOT EXISTS task_actions (
 action_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, chat_id TEXT NOT NULL,
 action_index INTEGER NOT NULL, action_description TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('started','completed','failed','skipped')), evidence_ref TEXT, note TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, UNIQUE(task_id,account_id,project_id,chat_id,action_index)
);
CREATE TRIGGER IF NOT EXISTS task_actions_no_update BEFORE UPDATE ON task_actions BEGIN SELECT RAISE(ABORT,'task action history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS task_actions_no_delete BEFORE DELETE ON task_actions BEGIN SELECT RAISE(ABORT,'task action history is retained'); END;
CREATE TABLE IF NOT EXISTS task_verifications (
 verification_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, chat_id TEXT NOT NULL,
 plan_artifact_id TEXT NOT NULL, plan_sha256 TEXT NOT NULL,
 overall_status TEXT NOT NULL CHECK(overall_status IN ('pass','partial','fail','unverified')),
 checks_json TEXT NOT NULL, report_artifact_id TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(plan_artifact_id) REFERENCES task_artifacts(artifact_id), FOREIGN KEY(report_artifact_id) REFERENCES task_artifacts(artifact_id)
);
CREATE TRIGGER IF NOT EXISTS task_verifications_no_update BEFORE UPDATE ON task_verifications BEGIN SELECT RAISE(ABORT,'task verification history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS task_verifications_no_delete BEFORE DELETE ON task_verifications BEGIN SELECT RAISE(ABORT,'task verification history is retained'); END;
'''


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dependency():
    if not SKILL_PATH.is_file() or not DEPENDENCY_PATH.is_file():
        raise RuntimeError("Pinned critical-thinking dependency is missing.")
    body = SKILL_PATH.read_text(encoding="utf-8")
    raw = body.encode("utf-8")
    manifest = json.loads(DEPENDENCY_PATH.read_text(encoding="utf-8"))
    actual_git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    if actual_git_blob != manifest.get("source_blob_sha"):
        raise RuntimeError("Vendored critical-thinking skill does not match its pinned Git blob SHA.")
    if manifest.get("source_commit") != "d1f23e2ad9dafd323940fc6b7a00f1700275d885":
        raise RuntimeError("Critical-thinking source commit does not match the expected pin.")
    if manifest.get("source_blob_sha") != "d7134969b124e39c04e343bed2ce2475f64b9a64":
        raise RuntimeError("Critical-thinking source blob does not match the expected pin.")
    return body, manifest, sha(body)


def init(con):
    con.executescript(SCHEMA)
    con.commit()


def get_task(con, task_id, account, project, chat):
    row = con.execute("SELECT * FROM task_runs WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?",
                      (task_id, account, project, chat)).fetchone()
    if not row:
        raise ValueError(f"Unknown task {task_id!r} in this scope.")
    return dict(row)


def emit(con, runtime, t, event_type, actor, state, note="", artifact_id=None, artifact_hash=None, metadata=None, from_state=None):
    before = t["state"] if from_state is None else from_state
    eid = "TE-" + os.urandom(8).hex()
    timestamp = now()
    con.execute("""INSERT INTO task_events(event_id,task_id,account_id,project_id,chat_id,event_type,actor,
        from_state,to_state,artifact_id,artifact_sha256,note,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid,t["task_id"],t["account_id"],t["project_id"],t["chat_id"],event_type,actor,before,state,
         artifact_id,artifact_hash,note,json.dumps(metadata or {},ensure_ascii=False),timestamp))
    con.execute("UPDATE task_runs SET state=?,updated_at=? WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?",
                (state,now(),t["task_id"],t["account_id"],t["project_id"],t["chat_id"]))
    con.commit()
    if runtime:
        provenance = actor if actor in {"user","assistant","system","external"} else "system"
        authority = "user_direct" if actor in {"user","delegated_human"} else ("system_process" if actor=="system" else "none")
        runtime.append_event(con,account=t["account_id"],project=t["project_id"],chat=t["chat_id"],
            event_type=event_type,provenance=provenance,authority=authority,inference_kind="process_event",
            truth_status="not_applicable",source_ref=artifact_id,content=note or event_type,
            metadata={"task_id":t["task_id"],"from_state":before,"to_state":state,"artifact_sha256":artifact_hash,**(metadata or {})})
    return {"event_id":eid,"event_type":event_type,"from_state":before,"to_state":state,"created_at":timestamp}

def get_artifact(con,t,aid):
    row=con.execute("""SELECT * FROM task_artifacts WHERE artifact_id=? AND task_id=? AND account_id=? AND project_id=? AND chat_id=?""",
                    (aid,t["task_id"],t["account_id"],t["project_id"],t["chat_id"])).fetchone()
    if not row: raise ValueError("Artifact not found within this task scope.")
    a=dict(row)
    if sha(a["content"]) != a["content_sha256"]: raise RuntimeError("Artifact content hash mismatch; refusing to proceed.")
    return a


def current_artifact(con,t,kind):
    aid=t["current_case_artifact_id"] if kind=="case_notes" else t["current_plan_artifact_id"]
    return get_artifact(con,t,aid) if aid else None


def latest_decision(con,t,kind,a):
    row=con.execute("""SELECT * FROM task_decisions WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?
       AND decision_type=? AND artifact_id=? AND artifact_sha256=? ORDER BY rowid DESC LIMIT 1""",
       (t["task_id"],t["account_id"],t["project_id"],t["chat_id"],kind,a["artifact_id"],a["content_sha256"])).fetchone()
    return dict(row) if row else None


def create(con,runtime,task_id,account,project,chat,request,model=None):
    if not all(isinstance(x,str) and x.strip() for x in (task_id,account,project,chat,request)):
        raise ValueError("Task ID, account, project, chat and request must be non-empty.")
    if con.execute("SELECT 1 FROM task_runs WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?",
                   (task_id,account,project,chat)).fetchone(): raise ValueError("Task ID already exists in this scope.")
    _,m,content_hash=dependency()
    stamp=now()
    con.execute("""INSERT INTO task_runs(task_id,account_id,project_id,chat_id,request,state,model_name,skill_commit,skill_blob_sha,
       current_case_artifact_id,current_plan_artifact_id,created_at,updated_at)
       VALUES(?,?,?,?,?,'created',?,?,?,NULL,NULL,?,?)""",
       (task_id,account,project,chat,request,model,m["source_commit"],m["source_blob_sha"],stamp,stamp))
    con.commit(); t=get_task(con,task_id,account,project,chat)
    ev=emit(con,runtime,t,"task.created","user","created",note="Task created: "+request,
            metadata={"model":model,"skill_commit":m["source_commit"],"skill_blob_sha":m["source_blob_sha"],"skill_content_sha256":content_hash})
    return {"task_id":task_id,"state":"created","skill_commit":m["source_commit"],"skill_blob_sha":m["source_blob_sha"],"skill_content_sha256":content_hash,"event":ev}


def put_artifact(con,runtime,t,kind,body,creator,based_case=None,metadata=None):
    if not isinstance(body,str) or not body.strip(): raise ValueError("Artifact content must be non-empty text.")
    count=con.execute("""SELECT COALESCE(MAX(version),0)+1 FROM task_artifacts WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=? AND kind=?""",
       (t["task_id"],t["account_id"],t["project_id"],t["chat_id"],kind)).fetchone()[0]
    aid="TA-"+os.urandom(8).hex(); _,m,content_hash=dependency(); body_hash=sha(body)
    con.execute("""INSERT INTO task_artifacts(artifact_id,task_id,account_id,project_id,chat_id,kind,version,content,content_sha256,
        based_on_case_sha256,dependency_commit,dependency_blob_sha,created_at,creator,metadata_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (aid,t["task_id"],t["account_id"],t["project_id"],t["chat_id"],kind,count,body,body_hash,based_case,
         m["source_commit"],m["source_blob_sha"],now(),creator,json.dumps(metadata or {},ensure_ascii=False)))
    con.commit()
    return {"artifact_id":aid,"kind":kind,"version":count,"content":body,"content_sha256":body_hash,
            "based_on_case_sha256":based_case,"dependency_commit":m["source_commit"],"dependency_blob_sha":m["source_blob_sha"]}


def submit_case(con,runtime,task_id,account,project,chat,body,creator="assistant",artifact_metadata=None):
    t=get_task(con,task_id,account,project,chat)
    previous_state=t["state"]
    if t["state"] in {"execution_started","execution_blocked","execution_completed","verification_recorded"}:
        raise ValueError("Cannot replace case notes after execution begins; create a new task.")
    a=put_artifact(con,runtime,t,"case_notes",body,creator,metadata=artifact_metadata)
    old_plan=t["current_plan_artifact_id"]
    con.execute("""UPDATE task_runs SET current_case_artifact_id=?,current_plan_artifact_id=NULL,updated_at=?
       WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?""",(a["artifact_id"],now(),task_id,account,project,chat))
    con.commit(); t=get_task(con,task_id,account,project,chat)
    ev=emit(con,runtime,t,"task.case_submitted",creator,"case_submitted","Case notes submitted; any earlier plan invalidated.",
       a["artifact_id"],a["content_sha256"],{"version":a["version"],"previous_plan_invalidated":bool(old_plan)},from_state=previous_state)
    return {k:v for k,v in {**a,"event":ev,"previous_plan_invalidated":bool(old_plan)}.items() if k!="content"}


def submit_plan(con,runtime,task_id,account,project,chat,body,creator="assistant",artifact_metadata=None):
    t=get_task(con,task_id,account,project,chat)
    if t["state"] in {"execution_started","execution_completed","verification_recorded"}:
        raise ValueError("Cannot replace plan after execution begins; create a new task.")
    case=current_artifact(con,t,"case_notes")
    if not case: raise ValueError("Submit case notes first.")
    cd=latest_decision(con,t,"case_notes",case)
    if not cd or cd["decision"]!="approve": raise ValueError("Cannot submit plan until the current case is approved.")
    a=put_artifact(con,runtime,t,"implementation_plan",body,creator,case["content_sha256"],artifact_metadata)
    con.execute("""UPDATE task_runs SET current_plan_artifact_id=?,updated_at=? WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?""",
       (a["artifact_id"],now(),task_id,account,project,chat))
    con.commit(); t=get_task(con,task_id,account,project,chat)
    ev=emit(con,runtime,t,"task.plan_submitted",creator,"plan_submitted","Plan is bound to the approved case-note hash.",
       a["artifact_id"],a["content_sha256"],{"version":a["version"],"based_on_case_sha256":case["content_sha256"]})
    return {k:v for k,v in {**a,"event":ev}.items() if k!="content"}


def decide(con,runtime,task_id,account,project,chat,kind,decision,note=""):
    t=get_task(con,task_id,account,project,chat)
    if kind not in {"case_notes","implementation_plan"} or decision not in {"approve","reject"}:
        raise ValueError("Invalid decision type or decision.")
    if t["state"] in {"execution_started","execution_blocked","execution_completed","verification_recorded"}: raise ValueError("Approvals are closed after execution begins.")
    a=current_artifact(con,t,kind)
    if not a: raise ValueError("No current artifact exists for this decision.")
    if kind=="implementation_plan":
        case=current_artifact(con,t,"case_notes")
        cd=latest_decision(con,t,"case_notes",case) if case else None
        if not case or not cd or cd["decision"]!="approve": raise ValueError("Current case must be approved before plan decision.")
        if a["based_on_case_sha256"]!=case["content_sha256"]: raise ValueError("Plan does not match current case-note hash.")
    did="TD-"+os.urandom(8).hex()
    con.execute("""INSERT INTO task_decisions(decision_id,task_id,account_id,project_id,chat_id,decision_type,artifact_id,artifact_sha256,
       decision,actor,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,'user',?,?)""",
       (did,task_id,account,project,chat,kind,a["artifact_id"],a["content_sha256"],decision,note,now()))
    con.commit()
    state=({"approve":"case_approved","reject":"case_rejected"} if kind=="case_notes" else {"approve":"plan_approved","reject":"plan_rejected"})[decision]
    ev=emit(con,runtime,t,"task."+kind+"."+decision,"user",state,note or decision,a["artifact_id"],a["content_sha256"],
            {"decision_id":did,"decision":decision,"decision_type":kind})
    return {"decision_id":did,"decision":decision,"artifact_id":a["artifact_id"],"artifact_sha256":a["content_sha256"],"event":ev}


def begin(con,runtime,task_id,account,project,chat):
    t=get_task(con,task_id,account,project,chat); case=current_artifact(con,t,"case_notes"); plan=current_artifact(con,t,"implementation_plan")
    if not case or not plan: raise ValueError("Execution requires case notes and implementation plan.")
    cd=latest_decision(con,t,"case_notes",case); pd=latest_decision(con,t,"implementation_plan",plan)
    if not cd or cd["decision"]!="approve": raise ValueError("Execution blocked: current case is not approved.")
    if not pd or pd["decision"]!="approve": raise ValueError("Execution blocked: current plan is not approved.")
    if plan["based_on_case_sha256"]!=case["content_sha256"]: raise ValueError("Execution blocked: plan-case hash mismatch.")
    if t["state"]!="plan_approved": raise ValueError("Execution blocked from task state "+t["state"]+".")
    ev=emit(con,runtime,t,"task.execution_started","system","execution_started","Execution authorised by both current hash-bound approvals.",
       plan["artifact_id"],plan["content_sha256"],{"case_artifact_id":case["artifact_id"],"case_sha256":case["content_sha256"],
       "plan_artifact_id":plan["artifact_id"],"plan_sha256":plan["content_sha256"],"case_decision_id":cd["decision_id"],"plan_decision_id":pd["decision_id"]})
    return {"task_id":task_id,"state":"execution_started","authorized":True,"case_sha256":case["content_sha256"],"plan_sha256":plan["content_sha256"],"event":ev}


def block(con,runtime,task_id,account,project,chat,reason):
    t=get_task(con,task_id,account,project,chat)
    if t["state"]!="execution_started":
        raise ValueError("A task can only be blocked or stopped after execution has started.")
    if not reason.strip(): raise ValueError("Provide a reason for the block or stop.")
    ev=emit(con,runtime,t,"task.execution_blocked","assistant","execution_blocked",reason,metadata={"reason":reason})
    return {"task_id":task_id,"state":"execution_blocked","reason":reason,"event":ev}


def log_action(con,runtime,task_id,account,project,chat,description,status,evidence_ref=None,note=""):
    t=get_task(con,task_id,account,project,chat)
    if t["state"]!="execution_started": raise ValueError("Actions can only be recorded during execution_started.")
    if status not in {"started","completed","failed","skipped"}: raise ValueError("Invalid action status.")
    idx=con.execute("SELECT COALESCE(MAX(action_index),0)+1 FROM task_actions WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?",
        (task_id,account,project,chat)).fetchone()[0]
    aid="ACT-"+os.urandom(8).hex()
    con.execute("""INSERT INTO task_actions(action_id,task_id,account_id,project_id,chat_id,action_index,action_description,status,evidence_ref,note,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(aid,task_id,account,project,chat,idx,description,status,evidence_ref,note,now()))
    con.commit(); ev=emit(con,runtime,t,"task.action_recorded","assistant","execution_started",description,metadata={"action_id":aid,"action_index":idx,"status":status,"evidence_ref":evidence_ref,"action_note":note})
    return {"action_id":aid,"action_index":idx,"status":status,"event":ev}


def complete(con,runtime,task_id,account,project,chat,summary,output_refs=None):
    t=get_task(con,task_id,account,project,chat)
    if t["state"]!="execution_started": raise ValueError("Only a started task may be completed.")
    if not summary.strip(): raise ValueError("Completion summary must include results, failures or blockers.")
    count=con.execute("SELECT COUNT(*) FROM task_actions WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=?",
        (task_id,account,project,chat)).fetchone()[0]
    ev=emit(con,runtime,t,"task.execution_completed","assistant","execution_completed",summary,
       metadata={"output_refs":output_refs or [],"action_count":count})
    return {"task_id":task_id,"state":"execution_completed","event":ev,"output_refs":output_refs or []}


def verify(con,runtime,task_id,account,project,chat,overall_status,checks,notes=""):
    t=get_task(con,task_id,account,project,chat)
    if t["state"]!="execution_completed": raise ValueError("Verification requires execution_completed.")
    if overall_status not in {"pass","partial","fail","unverified"}: raise ValueError("Invalid overall status.")
    if not isinstance(checks,list) or not checks: raise ValueError("At least one structured check is required.")
    statuses={"pass","fail","partial","not_tested"}
    for i,c in enumerate(checks):
        if not isinstance(c,dict) or not isinstance(c.get("criterion"),str) or not c["criterion"].strip(): raise ValueError(f"Check {i} requires criterion.")
        if c.get("status") not in statuses: raise ValueError(f"Check {i} has invalid status.")
        if c["status"]=="pass" and not c.get("evidence_refs"): raise ValueError(f"Passing check {i} requires evidence_refs.")
        if c["status"] in {"fail","partial","not_tested"} and not c.get("notes"): raise ValueError(f"Check {i} requires notes.")
        if c.get("evidence_refs") is not None and (not isinstance(c["evidence_refs"],list) or not all(isinstance(ref,str) and ref.strip() for ref in c["evidence_refs"])):
            raise ValueError(f"Check {i} evidence_refs must be a list of non-empty strings.")
    statuses_seen={c["status"] for c in checks}
    if overall_status=="pass" and statuses_seen!={"pass"}:
        raise ValueError("Overall pass requires every listed check to pass.")
    if overall_status=="fail" and "fail" not in statuses_seen:
        raise ValueError("Overall fail requires at least one failed check.")
    plan=current_artifact(con,t,"implementation_plan")
    payload={"task_id":task_id,"overall_status":overall_status,"plan_artifact_id":plan["artifact_id"],"plan_sha256":plan["content_sha256"],
       "checks":checks,"notes":notes,"warning":"A stored verification claim is not independent proof; inspect cited evidence and methods."}
    body="# Task Verification Report\n\n"+json.dumps(payload,ensure_ascii=False,indent=2)+"\n"
    report=put_artifact(con,runtime,t,"verification_report",body,"assistant",plan["based_on_case_sha256"],{"overall_status":overall_status})
    vid="TV-"+os.urandom(8).hex()
    con.execute("""INSERT INTO task_verifications(verification_id,task_id,account_id,project_id,chat_id,plan_artifact_id,plan_sha256,
       overall_status,checks_json,report_artifact_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
       (vid,task_id,account,project,chat,plan["artifact_id"],plan["content_sha256"],overall_status,json.dumps(checks,ensure_ascii=False),report["artifact_id"],now()))
    con.commit(); t=get_task(con,task_id,account,project,chat)
    ev=emit(con,runtime,t,"task.verification_recorded","assistant","verification_recorded","Verification status: "+overall_status,
       report["artifact_id"],report["content_sha256"],{"verification_id":vid,"overall_status":overall_status,"check_count":len(checks)})
    return {"verification_id":vid,"state":"verification_recorded","overall_status":overall_status,"report_artifact_id":report["artifact_id"],"event":ev}


def snapshot(con,task_id,account,project,chat):
    t=get_task(con,task_id,account,project,chat)
    def allrows(sql,args):
        return [dict(r) for r in con.execute(sql,args).fetchall()]
    args=(task_id,account,project,chat)
    arts=allrows("SELECT * FROM task_artifacts WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=? ORDER BY rowid",args)
    for a in arts:
        if sha(a["content"])!=a["content_sha256"]: raise RuntimeError("Artifact content hash mismatch.")
        a["metadata"]=json.loads(a.pop("metadata_json"))
    dec=allrows("SELECT * FROM task_decisions WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=? ORDER BY rowid",args)
    acts=allrows("SELECT * FROM task_actions WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=? ORDER BY action_index",args)
    evs=allrows("SELECT * FROM task_events WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=? ORDER BY seq",args)
    for e in evs: e["metadata"]=json.loads(e.pop("metadata_json"))
    ver=allrows("SELECT * FROM task_verifications WHERE task_id=? AND account_id=? AND project_id=? AND chat_id=? ORDER BY rowid",args)
    for v in ver: v["checks"]=json.loads(v.pop("checks_json"))
    body,manifest,content_hash=dependency()
    return {"task":t,"artifacts":arts,"decisions":dec,"actions":acts,"events":evs,"verifications":ver,
       "dependency":{"source_repo":manifest["source_repo"],"source_path":manifest["source_path"],"source_commit":manifest["source_commit"],
       "source_blob_sha":manifest["source_blob_sha"],"content_sha256":content_hash,"license":manifest["upstream_license"],"license_url":manifest["license"]}}


def export_markdown(s):
    t=s["task"]; d=s["dependency"]; lines=[
      "# AEL Task Audit — "+t["task_id"],"", "**State:** "+t["state"],"**Scope:** "+t["account_id"]+" / "+t["project_id"]+" / "+t["chat_id"],
      "**Created:** "+t["created_at"],"**Critical-thinking source commit:** "+d["source_commit"],"**Source blob SHA:** "+d["source_blob_sha"],
      "**Bundled skill SHA-256:** "+d["content_sha256"],"**Source URL:** "+d["source_repo"]+"/blob/"+d["source_commit"]+"/"+d["source_path"],
      "**License:** "+d["license"]+" ("+d["license_url"]+")","","## Original request","",t["request"],"","## Artifacts",""]
    for a in s["artifacts"]:
        lines += ["### "+a["kind"]+" v"+str(a["version"]),"Artifact ID: "+a["artifact_id"],"SHA-256: "+a["content_sha256"],
          "Creator: "+a["creator"],"Based on case SHA-256: "+str(a["based_on_case_sha256"] or "not applicable"),"Metadata: "+json.dumps(a["metadata"],ensure_ascii=False),"",a["content"],""]
    lines += ["## Decisions",""]
    for x in s["decisions"]: lines.append("- "+x["created_at"]+": "+x["decision"]+" "+x["decision_type"]+" by "+x["actor"]+" on artifact "+x["artifact_id"]+" hash "+x["artifact_sha256"]+". Note: "+(x["note"] or "(none)"))
    if not s["decisions"]: lines.append("No decisions recorded.")
    lines += ["","## Execution actions",""]
    for x in s["actions"]: lines.append("- #"+str(x["action_index"])+" "+x["status"]+": "+x["action_description"]+"; evidence="+str(x["evidence_ref"] or "(none)")+"; note="+(x["note"] or "(none)"))
    if not s["actions"]: lines.append("No execution actions recorded.")
    lines += ["","## Verification",""]
    for x in s["verifications"]:
        lines.append("- "+x["overall_status"]+" for plan "+x["plan_artifact_id"]+" hash "+x["plan_sha256"]+"; report "+x["report_artifact_id"])
        for c in x["checks"]: lines.append("  - "+c["status"]+": "+c["criterion"]+"; evidence="+", ".join(c.get("evidence_refs",[]))+"; notes="+c.get("notes",""))
    if not s["verifications"]: lines.append("No verification record exists.")
    lines += ["","## Event chronology",""]
    for x in s["events"]: lines.append("- #"+str(x["seq"])+" "+x["created_at"]+" "+x["event_type"]+" ("+x["actor"]+"): "+str(x["from_state"])+" -> "+x["to_state"]+"; artifact="+str(x["artifact_id"] or "-")+"; hash="+str(x["artifact_sha256"] or "-")+"; "+(x["note"] or ""))
    lines += ["","## Audit limitations","",
      "- This record shows what the runtime recorded; it is not cryptographic proof that model-generated claims are true.",
      "- Passing checks must point to evidence; reviewers still need to inspect that evidence.",
      "- This prototype does not execute arbitrary external actions or prevent a separate agent from acting outside the runtime.",
      "- The critical-thinking skill is provisional. Pinning ensures reproducibility, not proven competence.",""]
    return "\n".join(lines)


def build_prompt(con,t,runtime,kind):
    skill,manifest,skill_hash=dependency()
    if kind=="case_notes":
        request=("Investigate the user's task and write detailed case notes for precommitment review. Apply the bundled Critical Thinking skill as flexible guidance, not a rigid checklist. Include task interpretation and boundaries, observations versus assumptions, sources searched and claim support, plausible alternatives, attempts to challenge your preferred account, unresolved issues, risk and a clear recommendation. Do not write the implementation plan yet. Be explicit about what you did not verify.\n\nUSER TASK:\n"+t["request"])
        context="PINNED CRITICAL-THINKING SKILL (follow as guidance):\n"+skill
        return context,request,skill_hash
    case=current_artifact(con,t,"case_notes")
    if not case: raise ValueError("No current case notes.")
    cd=latest_decision(con,t,"case_notes",case)
    if not cd or cd["decision"]!="approve": raise ValueError("Generate a plan only after the current case is approved.")
    request=("Using the approved case notes, propose a concrete implementation plan. Specify actions in order, expected outputs, preconditions, constraints and permissions, risks and failure handling, what counts as completion, and how each important claim/action will be verified. Mark irreversible or consequential actions and require explicit approval for changes outside scope. Do not execute the plan.\n\nORIGINAL USER TASK:\n"+t["request"]+"\n\nAPPROVED CASE NOTES:\n"+case["content"])
    return "PINNED CRITICAL-THINKING SKILL (follow as guidance):\n"+skill,request,skill_hash


def add_cli_parser(sub):
    p=sub.add_parser("task",help="Task-level critical-thinking precommitment and audit workflow")
    s=p.add_subparsers(dest="task_cmd",required=True)
    x=s.add_parser("create"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--request",required=True); x.add_argument("--model")
    x=s.add_parser("generate-case",help="Use local Ollama and the pinned skill to generate case notes for review"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--model",required=True); x.add_argument("--endpoint",default="http://127.0.0.1:11434"); x.add_argument("--timeout",type=float,default=120); x.add_argument("--out",required=True)
    x=s.add_parser("submit-case"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--content-file",required=True); x.add_argument("--creator",choices=["assistant","user"],default="assistant")
    x=s.add_parser("decide-case"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--decision",choices=["approve","reject"],required=True); x.add_argument("--note",default="")
    x=s.add_parser("generate-plan",help="Use local Ollama and the pinned skill to generate an implementation plan for review"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--model",required=True); x.add_argument("--endpoint",default="http://127.0.0.1:11434"); x.add_argument("--timeout",type=float,default=120); x.add_argument("--out",required=True)
    x=s.add_parser("submit-plan"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--content-file",required=True); x.add_argument("--creator",choices=["assistant","user"],default="assistant")
    x=s.add_parser("decide-plan"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--decision",choices=["approve","reject"],required=True); x.add_argument("--note",default="")
    x=s.add_parser("begin"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True)
    x=s.add_parser("block",help="Record that approved execution is blocked or stopped")
    x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--reason",required=True)
    x=s.add_parser("log-action"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--description",required=True); x.add_argument("--status",choices=["started","completed","failed","skipped"],required=True); x.add_argument("--evidence-ref"); x.add_argument("--note",default="")
    x=s.add_parser("complete"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--summary",required=True); x.add_argument("--output-ref",nargs="*",default=[])
    x=s.add_parser("verify"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--overall-status",choices=["pass","partial","fail","unverified"],required=True); x.add_argument("--checks-file",required=True); x.add_argument("--notes",default="")
    x=s.add_parser("export"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True); x.add_argument("--out",required=True)
    x=s.add_parser("show"); x.add_argument("--project",required=True); x.add_argument("--chat",required=True); x.add_argument("--id",required=True)


def dispatch(con,runtime,a,account):
    init(con); task_id,project,chat=a.id,a.project,a.chat
    if a.task_cmd=="create":
        result=create(con,runtime,task_id,account,project,chat,a.request,a.model)
    elif a.task_cmd in {"generate-case","generate-plan"}:
        t=get_task(con,task_id,account,project,chat); kind="case_notes" if a.task_cmd=="generate-case" else "implementation_plan"
        context,message,skill_hash=build_prompt(con,t,runtime,kind)
        if not a.model.strip(): raise ValueError("Model name must be non-empty.")
        response=runtime.ollama_chat({"working_context":context,"current_user_message":message},model=a.model,base_url=a.endpoint,timeout=a.timeout)
        out=Path(a.out).expanduser().resolve(); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(response["content"],encoding="utf-8")
        generation_metadata={"provider":"ollama-local","model":response["model"],"endpoint_host":response.get("endpoint_host"),
            "generated_by_model":True,"skill_content_sha256":skill_hash,"output_path":str(out)}
        result=submit_case(con,runtime,task_id,account,project,chat,response["content"],artifact_metadata=generation_metadata) if kind=="case_notes" else submit_plan(con,runtime,task_id,account,project,chat,response["content"],artifact_metadata=generation_metadata)
        result.update({"out":str(out),"model":response["model"],"provider":"ollama-local","skill_content_sha256":skill_hash,"generated_by_model":True})
        result.pop("content",None)
    elif a.task_cmd=="submit-case":
        result=submit_case(con,runtime,task_id,account,project,chat,Path(a.content_file).expanduser().read_text(encoding="utf-8"),a.creator)
    elif a.task_cmd=="decide-case": result=decide(con,runtime,task_id,account,project,chat,"case_notes",a.decision,a.note)
    elif a.task_cmd=="submit-plan":
        result=submit_plan(con,runtime,task_id,account,project,chat,Path(a.content_file).expanduser().read_text(encoding="utf-8"),a.creator)
    elif a.task_cmd=="decide-plan": result=decide(con,runtime,task_id,account,project,chat,"implementation_plan",a.decision,a.note)
    elif a.task_cmd=="begin": result=begin(con,runtime,task_id,account,project,chat)
    elif a.task_cmd=="block": result=block(con,runtime,task_id,account,project,chat,a.reason)
    elif a.task_cmd=="log-action": result=log_action(con,runtime,task_id,account,project,chat,a.description,a.status,a.evidence_ref,a.note)
    elif a.task_cmd=="complete": result=complete(con,runtime,task_id,account,project,chat,a.summary,a.output_ref)
    elif a.task_cmd=="verify":
        checks=json.loads(Path(a.checks_file).expanduser().read_text(encoding="utf-8"))
        result=verify(con,runtime,task_id,account,project,chat,a.overall_status,checks,a.notes)
    elif a.task_cmd=="export":
        s=snapshot(con,task_id,account,project,chat); out=Path(a.out).expanduser().resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(export_markdown(s),encoding="utf-8")
        result={"task_id":task_id,"state":s["task"]["state"],"out":str(out),"sha256":sha(out.read_text(encoding="utf-8")),"file_exists":out.is_file()}
    elif a.task_cmd=="show":
        s=snapshot(con,task_id,account,project,chat); t=s["task"]
        result={"task":t,"dependency":s["dependency"],"current_case":t["current_case_artifact_id"],"current_plan":t["current_plan_artifact_id"],
                "artifact_count":len(s["artifacts"]),"decision_count":len(s["decisions"]),"action_count":len(s["actions"]),"event_count":len(s["events"])}
    else: raise ValueError("Unknown task subcommand.")
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return 0
