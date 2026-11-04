"""CT A/B logger adapter retaining the experiment's established contract."""
from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping
from .context import ContextValidationError, validate_manifest_context
from testing_logger.logger import (
    TestingLogger, LOGGER_VERSION, SCHEMA_VERSION, ZERO_HASH, utc_now,
    canonical_json, sha256_bytes, sha256_file,
)


CAPTURE_PROFILE = {
    "id": "ct-ab-runner-capture",
    "version": 1,
    "capabilities": [
        "append_only_jsonl_events",
        "event_sha256_chain",
        "event_stream_sha256_checksum",
        "artifact_sha256_and_size",
        "context_snapshot_binding",
        "model_request_lifecycle",
        "model_exchange_artifacts",
        "tool_dispatch_input_output_artifacts",
        "command_stdout_stderr_artifacts",
        "workspace_change_snapshots",
        "acceptance_test_results",
        "agent_recovery_and_loop_detection",
    ],
}


def _runner_source_provenance() -> tuple[str | None, bool | None]:
    """Return the checked-out implementation revision and clean-worktree state.

    Missing Git metadata is represented explicitly instead of guessed. A
    revision alone is not sufficient when the local worktree contains edits.
    """
    repo_root = Path(__file__).resolve().parents[2]
    revision: str | None = None
    clean: bool | None = None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        candidate = result.stdout.strip()
        if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", candidate):
            revision = candidate
    except (OSError, subprocess.SubprocessError):
        candidate = os.environ.get("GITHUB_SHA", "").strip()
        if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", candidate):
            revision = candidate
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        clean = not result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return revision, clean


def _build_run_provenance() -> dict[str, Any]:
    profile = dict(CAPTURE_PROFILE)
    profile["capabilities"] = list(CAPTURE_PROFILE["capabilities"])
    revision, clean = _runner_source_provenance()
    return {
        "capture_profile": profile,
        "capture_profile_sha256": sha256_bytes(canonical_json(profile)),
        "runner_implementation_revision": revision,
        "runner_worktree_clean": clean,
    }

class RunLogger(TestingLogger):
    """CT-specific manifest validation over the shared testing logger engine."""
    def __init__(self, run_dir: str | Path, workspace_root: str | Path, manifest: Mapping[str, Any]):
        required = {
            "run_id", "condition_label", "task_brief_sha256", "condition_config_sha256",
            "logger_version", "schema_version", "started_at_utc", "model", "environment",
            "resource_limits", "base_commit", "context_id", "context",
        }
        missing = required - set(manifest)
        if missing:
            raise ValueError(f"manifest missing fields: {sorted(missing)}")
        if manifest["condition_label"] not in {"A", "B", "REHEARSAL-A", "REHEARSAL-B"}:
            raise ValueError("condition_label must be blinded A/B or explicit rehearsal label")
        try:
            context = validate_manifest_context(manifest)
        except ContextValidationError as exc:
            raise ValueError(f"invalid run context: {exc}") from exc
        if context is None:
            raise ValueError("CT run manifests require a context_id and embedded context snapshot")
        context_hash = sha256_bytes(canonical_json(context))
        provenance = _build_run_provenance()
        # Provenance is produced by this adapter; caller-supplied values may
        # not silently override the implementation/capture identity.
        for field, value in provenance.items():
            if field in manifest and manifest[field] != value:
                raise ValueError(f"manifest {field} does not match current runner provenance")
        stored_manifest = dict(manifest)
        stored_manifest.update(provenance)
        profile = provenance["capture_profile"]
        super().__init__(
            run_dir,
            workspace_root,
            stored_manifest,
            run_started_payload={
                "context_id": context["context_id"],
                "context_sha256": context_hash,
                "capture_profile_id": profile["id"],
                "capture_profile_version": profile["version"],
                "capture_profile_sha256": provenance["capture_profile_sha256"],
                "runner_implementation_revision": provenance["runner_implementation_revision"],
                "runner_worktree_clean": provenance["runner_worktree_clean"],
            },
        )

__all__ = [
    "RunLogger", "TestingLogger", "LOGGER_VERSION", "SCHEMA_VERSION", "ZERO_HASH",
    "utc_now", "canonical_json", "sha256_bytes", "sha256_file",
]
