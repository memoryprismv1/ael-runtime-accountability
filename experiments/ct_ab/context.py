"""Load and validate durable test-context records for Q-Batch runs.

Context explains why a test exists. It is distinct from run evidence and from
later interpretation. Context records are versioned in context_catalog.json;
each new run embeds an exact snapshot in its manifest.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

CONTEXT_VERSION = "1.0"
PACKAGE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = PACKAGE_DIR / "context_catalog.json"

REQUIRED_CONTEXT_FIELDS = {
    "context_id", "version", "summary", "description", "purpose",
    "rationale", "hypothesis", "origin_refs", "created_at", "created_by",
}


class ContextValidationError(ValueError):
    """Raised when a context record is incomplete or malformed."""


def validate_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContextValidationError("context must be an object")
    missing = REQUIRED_CONTEXT_FIELDS - set(value)
    if missing:
        raise ContextValidationError(f"context missing fields: {sorted(missing)}")
    if not isinstance(value["context_id"], str) or not value["context_id"].strip():
        raise ContextValidationError("context_id must be a non-empty string")
    if not isinstance(value["version"], int) or value["version"] < 1:
        raise ContextValidationError("context version must be a positive integer")
    for field in ("summary", "description", "purpose", "rationale", "created_at", "created_by"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ContextValidationError(f"context {field} must be a non-empty string")
    if value["hypothesis"] is not None and not isinstance(value["hypothesis"], str):
        raise ContextValidationError("context hypothesis must be a string or null")
    refs = value["origin_refs"]
    if not isinstance(refs, list):
        raise ContextValidationError("context origin_refs must be an array")
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict) or not isinstance(ref.get("kind"), str) or not ref["kind"].strip() or not isinstance(ref.get("ref"), str) or not ref["ref"].strip():
            raise ContextValidationError(f"context origin_refs[{index}] must contain non-empty kind and ref")
    return dict(value)


def load_context(context_id: str, catalog_path: str | Path = CATALOG_PATH) -> dict[str, Any]:
    if not isinstance(context_id, str) or not context_id.strip():
        raise ContextValidationError("context_id must be a non-empty string")
    try:
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextValidationError(f"cannot read context catalog: {exc}") from exc
    if not isinstance(catalog, dict) or catalog.get("catalog_version") != CONTEXT_VERSION or not isinstance(catalog.get("contexts"), list):
        raise ContextValidationError("unsupported or malformed context catalog")
    matches = [item for item in catalog["contexts"] if isinstance(item, dict) and item.get("context_id") == context_id]
    if len(matches) != 1:
        raise ContextValidationError(f"expected exactly one context for {context_id!r}, found {len(matches)}")
    return validate_context(matches[0])


def validate_manifest_context(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    """Validate optional embedded context; None keeps historical manifests readable."""
    context = manifest.get("context")
    context_id = manifest.get("context_id")
    if context is None and context_id is None:
        return None
    if context is None or context_id is None:
        raise ContextValidationError("manifest context_id and context snapshot must appear together")
    snapshot = validate_context(context)
    if context_id != snapshot["context_id"]:
        raise ContextValidationError("manifest context_id does not match embedded context")
    return snapshot
