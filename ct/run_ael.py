#!/usr/bin/env python3
from __future__ import annotations
import os, subprocess, sys
from ael_environment import prepare_environment, REPOSITORY_ROOT

def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h","--help"}:
        print("Usage: python run_ael.py [--path ENVIRONMENT] {runtime|chat} [arguments]")
        print("Examples: python run_ael.py runtime --help")
        print("          python run_ael.py --path ct runtime task --help")
        print("          python run_ael.py --path ct chat")
        return 0 if args and args[0] in {"-h","--help"} else 2
    chosen=None
    if args[0]=="--path":
        if len(args)<3: print("Error: --path requires a value and entry point.",file=sys.stderr); return 2
        chosen=args[1]; del args[:2]
    elif args[0].startswith("--path="): chosen=args.pop(0).split("=",1)[1]
    entry=args.pop(0)
    if entry not in {"runtime","chat"}: print(f"Unknown entry point: {entry}",file=sys.stderr); return 2
    try: root,manifest,deps=prepare_environment(chosen if chosen is not None else os.environ.get("AEL_PATH",str(REPOSITORY_ROOT)))
    except (ValueError,RuntimeError) as exc: print(f"Environment validation failed: {exc}",file=sys.stderr); return 2
    target=root/("runtime.py" if entry=="runtime" else "ael_chat.py")
    env=os.environ.copy(); env["AEL_PATH"]=str(root); env["PYTHONPATH"]=str(root); env["PYTHONDONTWRITEBYTECODE"]="1"
    print(f"AEL experiment: {manifest['experiment_id']}",file=sys.stderr); print(f"AEL_PATH: {root}",file=sys.stderr)
    for name,item in deps.items(): print(f"Dependency {name}: {item['version']} ({'available' if item['available'] else 'optional and absent'})",file=sys.stderr)
    return subprocess.run([sys.executable,str(target),*args],cwd=root,env=env).returncode

if __name__=="__main__": raise SystemExit(main())
