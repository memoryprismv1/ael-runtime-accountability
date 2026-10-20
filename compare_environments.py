#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from ael_environment import REPOSITORY_ROOT,prepare_environment
LINE=re.compile(r"^(?P<test>test_[A-Za-z0-9_]+)\s+\((?P<class>[^)]+)\)\s+\.\.\.\s+(?P<status>ok|FAIL|ERROR|skipped.*)$",re.MULTILINE)
def parse_results(output):
    # unittest's parenthesized field is already the fully qualified test ID.
    return {m.group("class"):m.group("status").split()[0] for m in LINE.finditer(output)}
def pair(first,second,results):
    a,b=results[first],results[second]; common=sorted(set(a)&set(b))
    diffs=[{"test":t,first:a[t],second:b[t]} for t in common if a[t]!=b[t]]
    regressions=[x for x in diffs if x[first]=="ok" and x[second] in {"FAIL","ERROR","skipped"}]
    return {"environments":[first,second],"shared_test_count":len(common),"shared_test_status_differences":diffs,
      "baseline_pass_to_experiment_failure":regressions,"first_only_tests":sorted(set(a)-set(b)),
      "second_only_tests":sorted(set(b)-set(a)),"shared_tests_match":not diffs}
def parse_spec(spec):
    if "=" not in spec: raise argparse.ArgumentTypeError("Use NAME=PATH.")
    name,path=spec.split("=",1)
    if not name.strip() or not path.strip(): raise argparse.ArgumentTypeError("Use NAME=PATH.")
    return name.strip(),path.strip()
def run_suite(name,value):
    root,manifest,deps=prepare_environment(value); env=os.environ.copy(); env.update({"AEL_PATH":str(root),"PYTHONPATH":str(root),"PYTHONDONTWRITEBYTECODE":"1"})
    cmd=[sys.executable,"-m","unittest","discover","-s","tests","-v"]
    try: cp=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True,timeout=600)
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {"name":name,"path":str(root),"experiment_id":manifest["experiment_id"],"dependencies":deps,"command":cmd,
          "exit_code":124 if isinstance(exc,subprocess.TimeoutExpired) else 127,"suite_passed":False,"test_count_reported":None,"parsed_test_count":0,"tests":{},"stdout":"","stderr":str(exc)}
    output=cp.stdout+"\n"+cp.stderr; results=parse_results(output); m=re.search(r"Ran\s+(\d+)\s+tests?",output); reported=int(m.group(1)) if m else None
    complete=reported is not None and reported==len(results)
    return {"name":name,"path":str(root),"experiment_id":manifest["experiment_id"],"dependencies":deps,"command":cmd,"exit_code":cp.returncode,
      "suite_passed":cp.returncode==0 and complete,"test_count_reported":reported,"parsed_test_count":len(results),"test_parse_complete":complete,
      "tests":results,"stdout":cp.stdout,"stderr":cp.stderr}
def main(argv=None):
    p=argparse.ArgumentParser(description="Run identical regression suites in isolated AEL environments and compare their tests.")
    p.add_argument("--environment",action="append",type=parse_spec,metavar="NAME=PATH",help="Repeat for additional environments; default baseline=. and ct=ct.")
    p.add_argument("--out",help="Optional machine-readable JSON report.")
    args=p.parse_args(argv); specs=args.environment or [("baseline","."),("ct","ct")]
    if len(specs)<2: p.error("At least two environments are required.")
    names=[n for n,_ in specs]
    if len(set(names))!=len(names): p.error("Environment names must be unique.")
    suites={}
    for name,path in specs:
        print(f"\n=== Running {name} at {path} ===",flush=True); s=run_suite(name,path); suites[name]=s
        print(f"Experiment: {s['experiment_id']} | tests reported/parsed: {s['test_count_reported']}/{s['parsed_test_count']} | exit: {s['exit_code']}")
        if s["stderr"].strip(): print(s["stderr"].rstrip())
        if s["stdout"].strip(): print(s["stdout"].rstrip())
    results={n:s["tests"] for n,s in suites.items()}; pairs=[pair(names[i],names[j],results) for i in range(len(names)) for j in range(i+1,len(names))]
    overall=all(s["suite_passed"] for s in suites.values()) and all(x["shared_tests_match"] for x in pairs)
    try:
        rev=subprocess.run(["git","rev-parse","HEAD"],cwd=REPOSITORY_ROOT,capture_output=True,text=True,timeout=5)
        rev=rev.stdout.strip() if rev.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired): rev=None
    report={"schema_version":1,"created_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"repository_revision":rev,
      "method":"Identical unittest command run in isolated environment roots using each tree's own import path and inherited AEL_PATH.",
      "interpretation_limit":"Regression testing only; does not prove CT improves reasoning. Model-output evaluation needs fixed cases and controlled model/version/settings.",
      "suites":suites,"pairwise_comparisons":pairs,"overall_passed":overall}
    if args.out:
        out=Path(args.out).expanduser()
        if not out.is_absolute(): out=REPOSITORY_ROOT/out
        out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(f"\nReport written: {out}")
    print("\n=== SUMMARY ==="); print(json.dumps({"overall_passed":overall,"suites":{n:{"passed":s["suite_passed"],"reported":s["test_count_reported"],"parsed":s["parsed_test_count"]} for n,s in suites.items()},"pairwise_comparisons":[{"environments":x["environments"],"shared_test_count":x["shared_test_count"],"shared_tests_match":x["shared_tests_match"],"shared_test_status_differences":x["shared_test_status_differences"],"regressions":x["baseline_pass_to_experiment_failure"]} for x in pairs]},indent=2))
    return 0 if overall else 1
if __name__=="__main__": raise SystemExit(main())
