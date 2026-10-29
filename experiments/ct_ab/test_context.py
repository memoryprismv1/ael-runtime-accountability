"""Load and validate the durable test-context catalogue used by Q-Batch runs.

Context is explanatory provenance, not a test result. Run manifests embed a
snapshot so later edits to the catalogue cannot silently rewrite old runs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

PACKAGE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = PACKAGE_DIR / "test_contexts.json"
REQUIRED_FIELDS = {
    "context_id", "test_id", "version", "summary", "description", "purpose",
    "rationale", "origin_refs", "created_at", "created_by", "related_tests",
}


def validate_test_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("test_context must be an object")
    missing = REQUIRED_FIELDS - set(value)
    if missing:
        raise ValueError(f"test_context missing fields: {sorted(missing)}")
    for key in ("context_id", "test_id", "summary", "description", "purpose", "rationale", "created_at", "created_by"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError(f"test_context.{key} must be a non-empty string")
    if not isinstance(value["version"], int) or value["version"] < 1:
        raise ValueError("test_context.version must be a positive integer")
    if "hypothesis" in value and value["hypothesis"] is not None and not isinstance(value["hypothesis"], str):
        raise ValueError("test_context.hypothesis must be a string or null")
    if not isinstance(value["origin_refs"], list):
        raise ValueError("test_context.origin_refs must be a list")
    for index, ref in enumerate(value["origin_refs"]):
        if not isinstance(ref, dict) or not all(isinstance(ref.get(k), str) and ref[k].strip() for k in ("kind", "ref", "description")):
            raise ValueError(f"test_context.origin_refs[{index}] must include non-empty kind, ref, and description")
    if not isinstance(value["related_tests"], list) or not all(isinstance(item, str) and item.strip() for item in value["related_tests"]):
        raise ValueError("test_context.related_tests must be a list of non-empty strings")
    return dict(value)


def load_test_context(test_id: str) -> dict[str, Any]:
    if not isinstance(test_id, str) or not test_id.strip():
        raise ValueError("test_id is required to load test context")
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "1.0" or not isinstance(catalog.get("contexts"), list):
        raise ValueError("invalid test context catalogue")
    matches = [item for item in catalog["contexts"] if isinstance(item, dict) and item.get("test_id") == test_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one context for test_id {test_id!r}; found {len(matches)}")
    context = validate_test_context(matches[0])
    ids = [item.get("test_id") for item in catalog["contexts"] if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        raise ValueError("test context catalogue contains duplicate test_id values")
    return context
