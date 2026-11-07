"""CSV fixtures for deterministic multi-user AEL tests and local chat setup."""
from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Any

from .config import VALID_IDENTITY_SOURCES, VALID_PARTICIPANT_TYPES
from .ledger import register_participant

REQUIRED_COLUMNS = {
    "fixture_key", "participant_type", "identity_source", "display_name"
}
OPTIONAL_COLUMNS = {"issuer", "external_id", "participant_id"}


def import_participants_csv(
    con,
    csv_path: str | Path,
    *,
    account: str = "default",
) -> dict[str, Any]:
    """Register participants from CSV without implicitly adding them to a chat.

    Organisation IDs are namespaced by issuer. Self-generated IDs are
    deterministic for (account, fixture_key), so repeated imports are
    idempotent. Provider/system identities must supply participant_id.
    """
    path = Path(csv_path).expanduser()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Participant CSV must have a header row")
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Participant CSV is missing required columns: {', '.join(missing)}")
        unknown = sorted(set(reader.fieldnames) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS)
        if unknown:
            raise ValueError(f"Unknown participant CSV columns: {', '.join(unknown)}")
        rows = list(reader)

    if not rows:
        raise ValueError("Participant CSV contains no participant rows")

    # Validate the whole file before the first write. This prevents a typo in a
    # late row leaving a partially imported roster.
    seen_keys: set[str] = set()
    prepared: list[dict[str, str]] = []
    for line_number, raw in enumerate(rows, start=2):
        row = {key: (value or "").strip() for key, value in raw.items() if key}
        fixture_key = row.get("fixture_key", "")
        if not fixture_key:
            raise ValueError(f"CSV row {line_number}: fixture_key must be non-empty")
        if fixture_key in seen_keys:
            raise ValueError(f"CSV row {line_number}: duplicate fixture_key {fixture_key!r}")
        seen_keys.add(fixture_key)

        participant_type = row.get("participant_type", "")
        identity_source = row.get("identity_source", "")
        if participant_type not in VALID_PARTICIPANT_TYPES:
            raise ValueError(
                f"CSV row {line_number}: participant_type must be one of {sorted(VALID_PARTICIPANT_TYPES)}"
            )
        if identity_source not in VALID_IDENTITY_SOURCES:
            raise ValueError(
                f"CSV row {line_number}: identity_source must be one of {sorted(VALID_IDENTITY_SOURCES)}"
            )
        if not row.get("display_name"):
            raise ValueError(f"CSV row {line_number}: display_name must be non-empty")

        if identity_source == "organisation":
            if not row.get("issuer") or not row.get("external_id"):
                raise ValueError(
                    f"CSV row {line_number}: organisation identity requires issuer and external_id"
                )
            if row.get("participant_id"):
                expected = f"org:{row['issuer']}:{row['external_id']}"
                if row["participant_id"] != expected:
                    raise ValueError(
                        f"CSV row {line_number}: participant_id must match {expected!r}"
                    )
        elif identity_source == "self_generated":
            if row.get("issuer") or row.get("external_id"):
                raise ValueError(
                    f"CSV row {line_number}: self_generated identity cannot carry issuer/external_id"
                )
            if not row.get("participant_id"):
                stable = uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"ael-participant-fixture:{account}:{fixture_key}",
                )
                row["participant_id"] = f"ael:participant:{stable}"
        elif not row.get("participant_id"):
            raise ValueError(
                f"CSV row {line_number}: {identity_source} identity requires participant_id"
            )

        prepared.append(row)

    participants: list[dict[str, Any]] = []
    by_key: dict[str, str] = {}
    con.execute("BEGIN IMMEDIATE")
    try:
        for row in prepared:
            participant = register_participant(
                con,
                account=account,
                participant_id=row.get("participant_id") or None,
                participant_type=row["participant_type"],
                identity_source=row["identity_source"],
                issuer=row.get("issuer") or None,
                external_id=row.get("external_id") or None,
                display_name=row["display_name"],
                metadata={"fixture_key": row["fixture_key"], "source_file": path.name},
                _commit=False,
            )
            participant_id = participant["participant_id"]
            by_key[row["fixture_key"]] = participant_id
            participants.append({
                "fixture_key": row["fixture_key"],
                "participant_id": participant_id,
                "participant_type": participant["participant_type"],
                "identity_source": participant["identity_source"],
                "display_name": participant["display_name"],
            })
        con.commit()
    except Exception:
        con.rollback()
        raise

    return {
        "account_id": account,
        "source": str(path),
        "registered_count": len(participants),
        "participants": participants,
        "by_fixture_key": by_key,
        "membership_created": False,
    }
