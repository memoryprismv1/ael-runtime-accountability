"""Shared output-path safety checks and workspace-rooted artifact reads."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath


class WorkspaceArtifactError(ValueError):
    """A workspace-relative artifact cannot be safely or faithfully read."""


def read_workspace_artifact(workspace_root: str | Path, relative_path: str | Path) -> dict:
    """Read a UTF-8 text artifact beneath a workspace root and hash its exact bytes.

    The returned content preserves newline distinctions (including CRLF). Symlinks
    that resolve outside the workspace are rejected. This is a path/provenance
    guard, not an OS sandbox against another process changing the filesystem.
    """
    raw_path = str(relative_path)
    if not raw_path or not raw_path.strip() or chr(0) in raw_path:
        raise WorkspaceArtifactError("Artifact path must be a non-empty relative path")

    # Treat either slash convention as a separator, including Windows traversal on POSIX.
    portable_path = raw_path.replace(chr(92), "/")
    posix_path = PurePosixPath(portable_path)
    windows_path = PureWindowsPath(raw_path)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise WorkspaceArtifactError("Artifact path must be workspace-relative")
    parts = posix_path.parts
    if not parts or any(part == ".." for part in parts):
        raise WorkspaceArtifactError("Artifact path must not contain parent traversal")

    try:
        root = Path(workspace_root).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise WorkspaceArtifactError(f"Workspace root cannot be resolved: {exc}") from exc
    if not root.is_dir():
        raise WorkspaceArtifactError("Workspace root must be an existing directory")

    try:
        resolved = root.joinpath(*parts).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise WorkspaceArtifactError(f"Workspace artifact cannot be resolved: {exc}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkspaceArtifactError("Artifact path resolves outside the workspace root") from exc
    if not resolved.is_file():
        raise WorkspaceArtifactError("Workspace artifact must be a regular file")

    try:
        raw_bytes = resolved.read_bytes()
    except OSError as exc:
        raise WorkspaceArtifactError(f"Workspace artifact cannot be read: {exc}") from exc
    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceArtifactError("Workspace artifact is not valid UTF-8 text") from exc

    return {
        "relative_path": PurePosixPath(*parts).as_posix(),
        "content": content,
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "byte_length": len(raw_bytes),
        "encoding": "utf-8",
    }


def ensure_distinct_output_paths(primary: str | Path, audit: str | Path) -> tuple[Path, Path]:
    """Resolve and validate separate artifact and runtime-audit destinations."""
    primary_path = Path(primary).expanduser().resolve()
    audit_path = Path(audit).expanduser().resolve()
    if primary_path == audit_path:
        raise ValueError('Response/model-input output and audit sidecar must use different file paths')
    return primary_path, audit_path
