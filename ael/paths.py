"""Shared output-path safety checks."""
from __future__ import annotations
from pathlib import Path

def ensure_distinct_output_paths(primary: str | Path, audit: str | Path) -> tuple[Path, Path]:
    """Resolve and validate separate artifact and runtime-audit destinations."""
    primary_path = Path(primary).expanduser().resolve()
    audit_path = Path(audit).expanduser().resolve()
    if primary_path == audit_path:
        raise ValueError('Response/model-input output and audit sidecar must use different file paths')
    return primary_path, audit_path
