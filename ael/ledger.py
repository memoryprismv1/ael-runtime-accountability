"""Canonical, global AEL event ledger operations."""
from __future__ import annotations
import json
import sqlite3
from typing import Any
from .config import new_id, now, VALID_PROVENANCE, VALID_AUTHORITIES, VALID_INFERENCE_KINDS, VALID_TRUTH_STATUSES

def append_event(con: sqlite3.Connection, *, account='default', project: str, chat: str,
                 event_type: str, provenance: str, content: str, authority='none',
                 inference_kind='unspecified', truth_status='unverified', source_ref=None,
                 branch_id=None, strategy_key=None, metadata: dict | None = None) -> dict[str, Any]:
    """Append an immutable historical event. No event row is edited or deleted by runtime operations."""
    if provenance not in VALID_PROVENANCE:
        raise ValueError(f'provenance must be one of {sorted(VALID_PROVENANCE)}')
    if authority not in VALID_AUTHORITIES:
        raise ValueError(f'authority must be one of {sorted(VALID_AUTHORITIES)}')
    if inference_kind not in VALID_INFERENCE_KINDS:
        raise ValueError(f'inference_kind must be one of {sorted(VALID_INFERENCE_KINDS)}')
    if truth_status not in VALID_TRUTH_STATUSES:
        raise ValueError(f'truth_status must be one of {sorted(VALID_TRUTH_STATUSES)}')
    eid, ts = new_id('EV'), now()
    cur = con.execute('''INSERT INTO events(event_id,created_at,account_id,project_id,chat_id,event_type,provenance,authority,
      inference_kind,truth_status,source_ref,content,branch_id,strategy_key,metadata_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (eid, ts, account, project, chat, event_type, provenance, authority, inference_kind, truth_status,
       source_ref, content, branch_id, strategy_key, json.dumps(metadata or {}, ensure_ascii=False)))
    con.commit()
    return dict(con.execute('SELECT * FROM events WHERE seq=?', (cur.lastrowid,)).fetchone())


def scope_events(con, account: str, project: str, chat: str) -> list[dict]:
    rows = con.execute('''SELECT * FROM events WHERE account_id=? AND project_id=? AND chat_id=? ORDER BY seq''',
                       (account, project, chat)).fetchall()
    return [dict(r) for r in rows]
