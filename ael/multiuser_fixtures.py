"""Run a deterministic multi-participant workflow from CSV fixtures."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .config import SYSTEM_ACTOR_ID
from .ledger import (
    append_event, join_participant, leave_participant,
    participants_at_sequence, scope_events, scope_ledger,
)
from .participant_fixtures import import_participants_csv
from .branches import propose_branch, decide_branch


REQUIRED_STEP_COLUMNS = {"step", "action", "actor_key"}
OPTIONAL_STEP_COLUMNS = {
    "participant_key", "role", "workflow_id", "content", "event_type",
    "branch_id", "label", "tradeoff", "strategy_key", "status",
    "decision_path", "note",
}


def _read_steps(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Workflow CSV must have a header row")
        missing = sorted(REQUIRED_STEP_COLUMNS - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Workflow CSV is missing columns: {', '.join(missing)}")
        unknown = sorted(set(reader.fieldnames) - REQUIRED_STEP_COLUMNS - OPTIONAL_STEP_COLUMNS)
        if unknown:
            raise ValueError(f"Unknown workflow CSV columns: {', '.join(unknown)}")
        rows = [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]
    if not rows:
        raise ValueError("Workflow CSV contains no steps")
    expected = list(range(1, len(rows) + 1))
    try:
        actual = [int(row["step"]) for row in rows]
    except (KeyError, ValueError) as exc:
        raise ValueError("Workflow step values must be sequential integers starting at 1") from exc
    if actual != expected:
        raise ValueError(f"Workflow step values must be sequential {expected}; received {actual}")
    return rows


def run_workflow_csv(
    con,
    *,
    participants_csv: str | Path,
    workflow_csv: str | Path,
    account: str,
    project: str,
    chat: str,
) -> dict[str, Any]:
    """Import identities then execute explicit, ordered membership/action steps."""
    imported = import_participants_csv(con, participants_csv, account=account)
    ids = imported["by_fixture_key"]
    steps = _read_steps(workflow_csv)
    results: list[dict[str, Any]] = []

    def resolve(key: str, field: str) -> str:
        if key == "system":
            return SYSTEM_ACTOR_ID
        if not key or key not in ids:
            raise ValueError(f"Workflow references unknown {field} {key!r}")
        return ids[key]

    for row in steps:
        action = row["action"]
        actor_id = resolve(row["actor_key"], "actor_key")
        participant_key = row.get("participant_key", "")
        workflow_id = row.get("workflow_id") or None

        if action == "join":
            participant_id = resolve(participant_key, "participant_key")
            period = join_participant(
                con, account=account, project=project, chat=chat,
                participant_id=participant_id, role=row.get("role") or "participant",
                workflow_id=workflow_id, actor_id=actor_id,
                note=row.get("note") or f"{participant_key} joined the chat/workflow",
            )
            result = {
                "step": int(row["step"]), "action": action,
                "participant_key": participant_key, "actor_key": row["actor_key"],
                "event_boundary": period["started_by_event_id"],
                "effective_from_seq": period["effective_from_seq"],
                "role": period["role"],
            }
        elif action == "leave":
            participant_id = resolve(participant_key, "participant_key")
            period = leave_participant(
                con, account=account, project=project, chat=chat,
                participant_id=participant_id, workflow_id=workflow_id,
                actor_id=actor_id,
                note=row.get("note") or f"{participant_key} left the chat/workflow",
            )
            result = {
                "step": int(row["step"]), "action": action,
                "participant_key": participant_key, "actor_key": row["actor_key"],
                "event_boundary": period["ended_by_event_id"],
                "effective_until_seq": period["effective_until_seq"],
                "role": period["role"],
            }
        elif action == "message":
            participant_id = resolve(participant_key, "participant_key")
            if not row.get("content"):
                raise ValueError(f"Workflow step {row['step']}: message requires content")
            event = append_event(
                con, account=account, project=project, chat=chat,
                event_type=row.get("event_type") or "user_message",
                provenance="user", authority="user_direct",
                inference_kind="user_statement", truth_status="not_applicable",
                actor_id=participant_id, content=row["content"],
                metadata={"fixture_step": int(row["step"]), "fixture_key": participant_key},
            )
            result = {
                "step": int(row["step"]), "action": action,
                "participant_key": participant_key, "actor_id": participant_id,
                "event_id": event["event_id"], "seq": event["seq"],
            }
        elif action == "branch_proposed":
            branch_id = row.get("branch_id", "")
            if not branch_id or not row.get("label") or not row.get("strategy_key"):
                raise ValueError(f"Workflow step {row['step']}: branch_proposed requires branch_id, label and strategy_key")
            propose_branch(
                con, account=account, project=project, chat=chat,
                branch_id=branch_id, label=row["label"],
                tradeoff=row.get("tradeoff") or "Fixture branch",
                strategy_key=row["strategy_key"], actor_id=actor_id,
            )
            event = con.execute(
                "SELECT * FROM events WHERE account_id=? AND project_id=? AND chat_id=? AND event_type='branch.proposed' AND branch_id=? ORDER BY seq DESC LIMIT 1",
                (account, project, chat, branch_id),
            ).fetchone()
            result = {
                "step": int(row["step"]), "action": action,
                "actor_key": row["actor_key"], "actor_id": actor_id,
                "branch_id": branch_id, "event_id": event["event_id"], "seq": event["seq"],
            }
        elif action == "branch_decided":
            branch_id = row.get("branch_id", "")
            status = row.get("status", "")
            if not branch_id or status not in {"selected", "rejected", "completed"}:
                raise ValueError(f"Workflow step {row['step']}: branch_decided requires branch_id and a valid status")
            decide_branch(
                con, account=account, project=project, chat=chat,
                branch_id=branch_id, status=status, note=row.get("note", ""),
                decision_path=row.get("decision_path") or "direct", actor_id=actor_id,
            )
            event = con.execute(
                "SELECT * FROM events WHERE account_id=? AND project_id=? AND chat_id=? AND event_type=? AND branch_id=? ORDER BY seq DESC LIMIT 1",
                (account, project, chat, f"branch.{status}", branch_id),
            ).fetchone()
            result = {
                "step": int(row["step"]), "action": action,
                "actor_key": row["actor_key"], "actor_id": actor_id,
                "branch_id": branch_id, "status": status,
                "event_id": event["event_id"], "seq": event["seq"],
            }
        else:
            raise ValueError(f"Workflow step {row['step']}: unsupported action {action!r}")
        results.append(result)

    events = scope_events(con, account, project, chat)
    last_seq = max((event["seq"] for event in events), default=0)
    manager_keys = [
        p["fixture_key"] for p in imported["participants"]
        if p["fixture_key"].casefold() == "manager"
    ]
    manager_id = ids[manager_keys[0]] if manager_keys else None
    manager_present_seqs = []
    if manager_id:
        for event in events:
            members = participants_at_sequence(
                con, account=account, project=project, chat=chat,
                event_seq=event["seq"],
            )
            if any(member["participant_id"] == manager_id for member in members):
                manager_present_seqs.append(event["seq"])

    return {
        "schema_version": 1,
        "account_id": account,
        "project_id": project,
        "chat_id": chat,
        "participant_import": {
            "registered_count": imported["registered_count"],
            "membership_created": imported["membership_created"],
        },
        "steps": results,
        "last_event_seq": last_seq,
        "manager_participant_id": manager_id,
        "manager_present_event_seqs": manager_present_seqs,
        "manager_performed_actions": any(
            event["actor_id"] == manager_id for event in events
        ) if manager_id else None,
        "ledger": scope_ledger(con, account, project, chat),
    }


def write_receipt(receipt: dict[str, Any], out_path: str | Path) -> Path:
    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
