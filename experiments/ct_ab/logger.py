"""CT A/B logger adapter retaining the experiment's established contract."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from .context import ContextValidationError, validate_manifest_context
from testing_logger.logger import (
    TestingLogger, LOGGER_VERSION, SCHEMA_VERSION, ZERO_HASH, utc_now,
    canonical_json, sha256_bytes, sha256_file,
)

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
        super().__init__(
            run_dir,
            workspace_root,
            manifest,
            run_started_payload={
                "context_id": context["context_id"],
                "context_sha256": context_hash,
            },
        )

__all__ = [
    "RunLogger", "TestingLogger", "LOGGER_VERSION", "SCHEMA_VERSION", "ZERO_HASH",
    "utc_now", "canonical_json", "sha256_bytes", "sha256_file",
]
