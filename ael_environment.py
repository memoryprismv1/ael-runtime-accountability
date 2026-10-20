from __future__ import annotations
import hashlib, json, os
from pathlib import Path
from typing import Any

REPOSITORY_ROOT=Path(__file__).resolve().parent
MANIFEST_NAME="experiment.json"

def _within(path:Path,root:Path)->bool:
    try: path.resolve().relative_to(root.resolve()); return True
    except ValueError: return False

def resolve_environment_path(value:str|os.PathLike[str]|None=None,repository_root:Path=REPOSITORY_ROOT)->Path:
    base=repository_root.resolve()
    raw=value if value is not None else os.environ.get("AEL_PATH",str(base))
    candidate=Path(raw).expanduser()
    if not candidate.is_absolute(): candidate=base/candidate
    root=candidate.resolve()
    if not _within(root,base): raise ValueError(f"AEL_PATH must stay inside the repository: {root}")
    if not root.is_dir(): raise ValueError(f"AEL_PATH does not name a directory: {root}")
    for required in ("runtime.py","ael_chat.py",MANIFEST_NAME):
        if not (root/required).is_file(): raise ValueError(f"AEL_PATH is not a complete environment; missing {required}: {root}")
    return root

def load_manifest(environment_root:Path)->dict[str,Any]:
    path=environment_root/MANIFEST_NAME
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise RuntimeError(f"Cannot read experiment manifest {path}: {exc}") from exc
    if not isinstance(data,dict) or data.get("schema_version")!=1: raise RuntimeError(f"Unsupported or malformed experiment manifest: {path}")
    if not isinstance(data.get("experiment_id"),str) or not data["experiment_id"].strip(): raise RuntimeError(f"Experiment manifest needs a non-empty experiment_id: {path}")
    if not isinstance(data.get("requirements",{}),dict): raise RuntimeError(f"Experiment manifest requirements must be an object: {path}")
    return data

def _git_blob_sha(data:bytes)->str:
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def validate_dependencies(environment_root:Path,manifest:dict[str,Any]|None=None)->dict[str,dict[str,Any]]:
    root=environment_root.resolve()
    manifest=manifest if manifest is not None else load_manifest(root)
    requirements=manifest.get("requirements",{})
    if not isinstance(requirements,dict): raise RuntimeError("Experiment manifest requirements must be an object.")
    result={}
    for name,req in requirements.items():
        if not isinstance(name,str) or not name.strip() or not isinstance(req,dict): raise RuntimeError("Each dependency needs a non-empty name and object definition.")
        version,path,required=req.get("version"),req.get("path"),req.get("required",True)
        if not isinstance(version,str) or not version.strip(): raise RuntimeError(f"Dependency {name!r} needs an exact, non-empty version.")
        if not isinstance(path,str) or not path.strip(): raise RuntimeError(f"Dependency {name!r} needs a relative path.")
        if not isinstance(required,bool): raise RuntimeError(f"Dependency {name!r} required flag must be boolean.")
        target=(root/path).resolve()
        if not _within(target,root): raise RuntimeError(f"Dependency {name!r} path escapes its environment: {path}")
        blob,sha256=req.get("source_blob_sha"),req.get("sha256")
        if not blob and not sha256: raise RuntimeError(f"Dependency {name!r} must declare source_blob_sha or sha256 integrity.")
        if not target.is_file():
            if required: raise RuntimeError(f"Required dependency {name!r} is missing: {target}")
            result[name]={"version":version,"available":False,"reason":"file missing"}; continue
        data=target.read_bytes()
        if blob and _git_blob_sha(data)!=blob: raise RuntimeError(f"Dependency {name!r} Git blob SHA mismatch.")
        if sha256 and hashlib.sha256(data).hexdigest()!=sha256: raise RuntimeError(f"Dependency {name!r} SHA-256 mismatch.")
        commit=req.get("source_commit")
        if version.startswith("git:") and version!=f"git:{commit}": raise RuntimeError(f"Dependency {name!r} version does not match its pinned source_commit.")
        result[name]={"version":version,"available":True,"path":path,"source_commit":commit,"source_blob_sha":blob,"sha256":sha256}
    return result

def prepare_environment(value:str|os.PathLike[str]|None=None)->tuple[Path,dict[str,Any],dict[str,dict[str,Any]]]:
    root=resolve_environment_path(value); manifest=load_manifest(root); deps=validate_dependencies(root,manifest)
    return root,manifest,deps
