"""Auditable changes to external/shared context that is injected into a chat."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from .config import VALID_AUTHORITIES
from .ledger import append_event, scope_events


def record_context_intervention(
    con: sqlite3.Connection, *, account: str = 'default', project: str, chat: str,
    resource_id: str, resource_type: str, version: str, content: str,
    actor_id: str, authority: str, source_ref: str | None = None,
    expected_previous_sha256: str | None = None, note: str = '',
) -> dict[str, Any]:
    """Record a versioned external-context change without editing chat messages.

    The exact resource text is retained in the append-only event. Only the latest
    version of a resource is injected by the active-context projection; older
    versions remain retrievable in canonical history. The actor must be an active
    participant in this chat (or an explicitly identified system/service actor).
    """
    for name, value in (("resource_id", resource_id), ("resource_type", resource_type), ("version", version)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")
    if authority not in VALID_AUTHORITIES:
        raise ValueError(f"authority must be one of {sorted(VALID_AUTHORITIES)}")

    content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    previous = None
    for event in scope_events(con, account, project, chat):
        if event["event_type"] != "context.intervened":
            continue
        metadata = json.loads(event.get("metadata_json") or "{}")
        if metadata.get("resource_id") == resource_id:
            previous = (event, metadata)
    previous_hash = previous[1].get("content_sha256") if previous else None
    if expected_previous_sha256 is not None and expected_previous_sha256 != previous_hash:
        raise ValueError("Context resource changed since the expected previous hash; refresh before retrying")
    if previous and previous[1].get("content_sha256") == content_sha256:
        raise ValueError("Context intervention is a no-op: content hash is unchanged")
    metadata = {
        "resource_id": resource_id,
        "resource_type": resource_type,
        "version": version,
        "previous_version": previous[1].get("version") if previous else None,
        "previous_sha256": previous_hash,
        "content_sha256": content_sha256,
        "note": note,
    }
    return append_event(
        con, account=account, project=project, chat=chat,
        event_type="context.intervened", provenance="external", authority=authority,
        inference_kind="process_event", truth_status="not_applicable",
        content=content, actor_id=actor_id, source_ref=source_ref, metadata=metadata,
    )
