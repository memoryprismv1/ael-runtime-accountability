#!/usr/bin/env python3
"""AEL Runtime prototype V2: history, context projection, memory, branch and revision controls.

Standard library only. Includes an optional loopback-only Ollama adapter; not a complete AEL implementation.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import os
import sqlite3
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from math import ceil

# AEL_PATH is inherited from the experiment launcher; mixed-tree execution is refused.
AEL_PATH = Path(os.environ.get("AEL_PATH", Path(__file__).resolve().parent)).expanduser().resolve()
_RUNTIME_ROOT = Path(__file__).resolve().parent
if AEL_PATH != _RUNTIME_ROOT:
    raise RuntimeError(f"AEL_PATH ({AEL_PATH}) does not match this runtime file's tree ({_RUNTIME_ROOT}).")
from ael_environment import prepare_environment
_ACTIVE_ROOT, _ACTIVE_MANIFEST, _ACTIVE_DEPENDENCIES = prepare_environment(AEL_PATH)
if _ACTIVE_ROOT != _RUNTIME_ROOT:
    raise RuntimeError("Resolved environment root does not match this runtime's directory.")

SCHEMA = r'''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  account_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  provenance TEXT NOT NULL CHECK(provenance IN ('user','assistant','external','system')),
  authority TEXT NOT NULL DEFAULT 'none',
  inference_kind TEXT NOT NULL DEFAULT 'unspecified',
  truth_status TEXT NOT NULL DEFAULT 'unverified',
  source_ref TEXT,
  content TEXT NOT NULL,
  branch_id TEXT,
  strategy_key TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_events_scope ON events(account_id, project_id, chat_id, seq);
CREATE INDEX IF NOT EXISTS ix_events_branch ON events(branch_id, seq);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'event ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'event ledger is append-only'); END;
CREATE TABLE IF NOT EXISTS branches (
  branch_id TEXT NOT NULL,
  account_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  label TEXT NOT NULL,
  tradeoff TEXT NOT NULL,
  strategy_key TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  PRIMARY KEY(account_id, project_id, chat_id, branch_id)
);
CREATE TABLE IF NOT EXISTS memories (
  memory_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK(scope IN ('account','project')),
  project_id TEXT,
  tag TEXT NOT NULL,
  claim TEXT NOT NULL,
  source_event_seq INTEGER,
  stage TEXT NOT NULL DEFAULT 'shared_reference' CHECK(stage IN ('local_candidate','shared_reference','keepable','discarded')),
  usage_status TEXT NOT NULL DEFAULT 'not_pertinent_now' CHECK(usage_status IN ('use_when_relevant','never_try_again','maybe_later','not_pertinent_now')),
  state TEXT NOT NULL CHECK(state IN ('pending','active','dormant','reversed')),
  read_permission INTEGER NOT NULL DEFAULT 1 CHECK(read_permission IN (0,1)),
  influence_permission INTEGER NOT NULL DEFAULT 0 CHECK(influence_permission IN (0,1)),
  weight REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL,
  last_confirmed_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(source_event_seq) REFERENCES events(seq)
);
CREATE INDEX IF NOT EXISTS ix_memories_scope ON memories(account_id, scope, project_id, tag);
CREATE TABLE IF NOT EXISTS memory_candidates (
  candidate_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK(scope IN ('account','project')),
  project_id TEXT,
  origin_project_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  claim TEXT NOT NULL,
  source_event_seq INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('local_candidate','pushed','rejected')),
  usage_status TEXT NOT NULL DEFAULT 'not_pertinent_now' CHECK(usage_status IN ('use_when_relevant','never_try_again','maybe_later','not_pertinent_now')),
  weight REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(source_event_seq) REFERENCES events(seq)
);
CREATE INDEX IF NOT EXISTS ix_memory_candidates_scope ON memory_candidates(account_id, scope, project_id, chat_id, state);
CREATE TRIGGER IF NOT EXISTS memory_candidates_no_delete BEFORE DELETE ON memory_candidates BEGIN SELECT RAISE(ABORT, 'memory candidate history is retained'); END;
CREATE TABLE IF NOT EXISTS memory_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  from_state TEXT,
  to_state TEXT NOT NULL,
  from_stage TEXT,
  to_stage TEXT,
  from_usage_status TEXT,
  to_usage_status TEXT,
  action_origin TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_memory_events_id ON memory_events(memory_id, seq);
CREATE TRIGGER IF NOT EXISTS memory_events_no_update BEFORE UPDATE ON memory_events BEGIN SELECT RAISE(ABORT, 'memory event history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_events_no_delete BEFORE DELETE ON memory_events BEGIN SELECT RAISE(ABORT, 'memory event history is append-only'); END;
CREATE TABLE IF NOT EXISTS checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  account_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  last_event_seq INTEGER NOT NULL,
  markdown_path TEXT NOT NULL,
  json_path TEXT NOT NULL,
  snapshot_sha256 TEXT NOT NULL
);CREATE TABLE IF NOT EXISTS revision_proposals (
  proposal_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  base_version TEXT NOT NULL,
  base_sha256 TEXT,
  original_request TEXT NOT NULL,
  delta_summary TEXT NOT NULL,
  impact_summary TEXT NOT NULL,
  changed_sections_json TEXT NOT NULL,
  parent_revision_id TEXT,
  proposal_hash TEXT NOT NULL,
  source_ref TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_revision_scope ON revision_proposals(account_id, project_id, chat_id, created_at);
CREATE TRIGGER IF NOT EXISTS revision_proposals_no_update BEFORE UPDATE ON revision_proposals BEGIN SELECT RAISE(ABORT, 'revision proposals are immutable'); END;
CREATE TRIGGER IF NOT EXISTS revision_proposals_no_delete BEFORE DELETE ON revision_proposals BEGIN SELECT RAISE(ABORT, 'revision proposals are retained as history'); END;
CREATE TABLE IF NOT EXISTS revision_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  proposal_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  from_state TEXT,
  to_state TEXT NOT NULL CHECK(to_state IN ('proposed','accepted_for_expansion','rejected','rejected_reset','expanded')),
  proposal_hash TEXT NOT NULL,
  action_origin TEXT NOT NULL CHECK(action_origin IN ('user','assistant','external','system')),
  note TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(proposal_id) REFERENCES revision_proposals(proposal_id)
);
CREATE INDEX IF NOT EXISTS ix_revision_events_proposal ON revision_events(proposal_id, seq);
CREATE TRIGGER IF NOT EXISTS revision_events_no_update BEFORE UPDATE ON revision_events BEGIN SELECT RAISE(ABORT, 'revision event history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS revision_events_no_delete BEFORE DELETE ON revision_events BEGIN SELECT RAISE(ABORT, 'revision event history is append-only'); END;
CREATE TABLE IF NOT EXISTS revision_outputs (
  output_id TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  proposal_hash TEXT NOT NULL,
  artifact_version TEXT NOT NULL,
  content TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(proposal_id) REFERENCES revision_proposals(proposal_id)
);
CREATE INDEX IF NOT EXISTS ix_revision_outputs_proposal ON revision_outputs(proposal_id, created_at);
CREATE TRIGGER IF NOT EXISTS revision_outputs_no_update BEFORE UPDATE ON revision_outputs BEGIN SELECT RAISE(ABORT, 'expanded artifacts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS revision_outputs_no_delete BEFORE DELETE ON revision_outputs BEGIN SELECT RAISE(ABORT, 'expanded artifacts are retained as history'); END;
CREATE TABLE IF NOT EXISTS revision_conformance_checks (
  check_id TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  proposal_hash TEXT NOT NULL,
  base_sha256 TEXT,
  output_sha256 TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pass','fail','unverifiable')),
  report_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(proposal_id) REFERENCES revision_proposals(proposal_id)
);
CREATE INDEX IF NOT EXISTS ix_revision_conformance_proposal ON revision_conformance_checks(proposal_id, created_at);
CREATE TRIGGER IF NOT EXISTS revision_conformance_no_update BEFORE UPDATE ON revision_conformance_checks BEGIN SELECT RAISE(ABORT, 'conformance checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS revision_conformance_no_delete BEFORE DELETE ON revision_conformance_checks BEGIN SELECT RAISE(ABORT, 'conformance checks are retained as history'); END;
'''

VALID_PROVENANCE = {'user', 'assistant', 'external', 'system'}
VALID_AUTHORITIES = {'none', 'user_direct', 'user_ratified_recommendation', 'delegated_execution', 'system_process'}
VALID_INFERENCE_KINDS = {
    'unspecified', 'user_statement', 'decision', 'external_claim', 'inference',
    'generated_artifact', 'observation', 'hypothesis', 'factual_claim', 'process_event'
}
VALID_TRUTH_STATUSES = {'unverified', 'verified', 'disputed', 'not_applicable'}
VALID_USAGE_STATUSES = {'use_when_relevant', 'never_try_again', 'maybe_later', 'not_pertinent_now'}
BRANCH_REUSE_STATUSES = {'never_try_again', 'maybe_later', 'not_pertinent_now'}


def default_data_dir() -> Path:
    """Stable per-user data location, independent of which version folder is running."""
    configured = os.environ.get('AEL_RUNTIME_HOME')
    if configured:
        return Path(configured).expanduser()
    if os.name == 'nt':
        local_app_data = os.environ.get('LOCALAPPDATA')
        if local_app_data:
            return Path(local_app_data) / 'AELRuntime'
    return Path.home() / '.ael-runtime'


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def new_id(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex[:16]}'


def connect(db_path: str | Path) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    con.executescript(SCHEMA)
    # Backward-compatible migration from early V2 prototypes. Existing pending
    # memories were already shared as read-only references; existing active or
    # walk-back memories had already been promoted to account/project authority.
    memory_cols = {r['name'] for r in con.execute('PRAGMA table_info(memories)').fetchall()}
    if 'stage' not in memory_cols:
        con.execute("ALTER TABLE memories ADD COLUMN stage TEXT NOT NULL DEFAULT 'shared_reference' CHECK(stage IN ('local_candidate','shared_reference','keepable','discarded'))")
        con.execute("UPDATE memories SET stage=CASE WHEN state='pending' THEN 'shared_reference' ELSE 'keepable' END")
    # Usage disposition is separate from retention, lifecycle, truth, and influence.
    memory_cols = {r['name'] for r in con.execute('PRAGMA table_info(memories)').fetchall()}
    if 'usage_status' not in memory_cols:
        con.execute("ALTER TABLE memories ADD COLUMN usage_status TEXT NOT NULL DEFAULT 'not_pertinent_now' CHECK(usage_status IN ('use_when_relevant','never_try_again','maybe_later','not_pertinent_now'))")
        con.execute("UPDATE memories SET usage_status=CASE WHEN stage='keepable' AND state='active' AND influence_permission=1 THEN 'use_when_relevant' ELSE 'not_pertinent_now' END")
    candidate_cols = {r['name'] for r in con.execute('PRAGMA table_info(memory_candidates)').fetchall()}
    if 'usage_status' not in candidate_cols:
        con.execute("ALTER TABLE memory_candidates ADD COLUMN usage_status TEXT NOT NULL DEFAULT 'not_pertinent_now' CHECK(usage_status IN ('use_when_relevant','never_try_again','maybe_later','not_pertinent_now'))")
    mem_event_cols = {r['name'] for r in con.execute('PRAGMA table_info(memory_events)').fetchall()}
    for col in ('from_stage','to_stage','from_usage_status','to_usage_status'):
        if col not in mem_event_cols:
            con.execute(f'ALTER TABLE memory_events ADD COLUMN {col} TEXT')
    con.commit()
    return con


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


def branch_statuses(con, account: str, project: str, chat: str) -> dict[str, str]:
    result: dict[str, str] = {}
    rows = con.execute('''SELECT branch_id,event_type FROM events WHERE account_id=? AND project_id=? AND chat_id=?
      AND event_type IN ('branch.selected','branch.rejected','branch.completed') ORDER BY seq''',
      (account, project, chat)).fetchall()
    for row in rows:
        target = row['branch_id']
        if not target:
            continue
        result[target] = row['event_type'].split('.', 1)[1]
    return result


def propose_branch(con, *, account='default', project: str, chat: str, branch_id: str,
                   label: str, tradeoff: str, strategy_key: str, original_query: str | None = None) -> None:
    if con.execute('SELECT 1 FROM branches WHERE branch_id=? AND account_id=? AND project_id=? AND chat_id=?',
                   (branch_id, account, project, chat)).fetchone():
        raise ValueError(f'branch_id already exists: {branch_id}')
    if original_query and not con.execute(
        "SELECT 1 FROM events WHERE account_id=? AND project_id=? AND chat_id=? AND event_type='original_query' LIMIT 1",
        (account, project, chat)).fetchone():
        append_event(con, account=account, project=project, chat=chat, event_type='original_query', provenance='user',
                     authority='user_direct', inference_kind='user_statement', truth_status='not_applicable',
                     content=original_query, metadata={'purpose': 'restore query for clean branch rerun'})
    con.execute('''INSERT INTO branches(branch_id,account_id,project_id,chat_id,label,tradeoff,strategy_key,proposed_at)
      VALUES(?,?,?,?,?,?,?,?)''', (branch_id, account, project, chat, label, tradeoff, strategy_key, now()))
    con.commit()
    append_event(con, account=account, project=project, chat=chat, event_type='branch.proposed', provenance='system',
                 content=f'{label}\nTrade-off: {tradeoff}', branch_id=branch_id, strategy_key=strategy_key,
                 inference_kind='process_event', truth_status='not_applicable',
                 metadata={'strategy_key': strategy_key, 'original_query': original_query})


def reject_branch(con, *, account='default', project: str, chat: str, branch_id: str,
                  note: str, strategy_failure: bool = False, threshold: int = 3,
                  usage_status: str = 'not_pertinent_now') -> dict:
    b = con.execute('''SELECT * FROM branches WHERE branch_id=? AND account_id=? AND project_id=? AND chat_id=?''',
                    (branch_id, account, project, chat)).fetchone()
    if not b:
        raise ValueError(f'Unknown branch {branch_id!r} for this account/project/chat')
    if usage_status not in BRANCH_REUSE_STATUSES:
        raise ValueError(f'usage_status must be one of {sorted(BRANCH_REUSE_STATUSES)}')
    append_event(con, account=account, project=project, chat=chat, event_type='branch.rejected', provenance='user',
                 authority='user_direct', inference_kind='decision', truth_status='not_applicable',
                 content=note or 'User rejected this branch', branch_id=branch_id,
                 strategy_key=b['strategy_key'], metadata={'strategy_failure': strategy_failure, 'usage_status': usage_status})
    consecutive = 0
    if strategy_failure:
        rows = con.execute('''SELECT strategy_key,event_type,metadata_json FROM events WHERE account_id=? AND project_id=? AND chat_id=?
          AND event_type IN ('branch.selected','branch.rejected','branch.completed') ORDER BY seq DESC''', (account, project, chat)).fetchall()
        for row in rows:
            # A successful/finished branch or an ordinary rejection breaks a consecutive failure run.
            if row['event_type'] in {'branch.selected','branch.completed'}:
                break
            meta = json.loads(row['metadata_json'] or '{}')
            if not meta.get('strategy_failure') or row['strategy_key'] != b['strategy_key']:
                break
            consecutive += 1
    triggered = bool(strategy_failure and consecutive >= threshold)
    if triggered:
        append_event(con, account=account, project=project, chat=chat, event_type='circuit_breaker.triggered',
                     provenance='system', content=f'Clean-slate strategy required after {consecutive} rejections of strategy {b["strategy_key"]}.',
                     inference_kind='process_event', truth_status='not_applicable',
                     metadata={'strategy_key': b['strategy_key'], 'consecutive_rejections': consecutive, 'threshold': threshold})
    return {'branch_id': branch_id, 'strategy_key': b['strategy_key'], 'consecutive_strategy_rejections': consecutive,
            'circuit_breaker_triggered': triggered, 'threshold': threshold, 'usage_status': usage_status,
            'retained_in_history': True, 'active_branch_output_injected': False}


def decide_branch(con, *, account='default', project: str, chat: str, branch_id: str,
                  status: str, note: str = '', decision_path: str = 'direct', strategy_failure=False,
                  threshold: int = 3, usage_status: str = 'not_pertinent_now') -> dict | None:
    if status not in {'selected', 'rejected', 'completed'}:
        raise ValueError('status must be selected, rejected, or completed')
    if decision_path not in {'direct', 'accepted_recommendation', 'system'}:
        raise ValueError('decision_path must be direct, accepted_recommendation, or system')
    b = con.execute('''SELECT * FROM branches WHERE branch_id=? AND account_id=? AND project_id=? AND chat_id=?''',
                    (branch_id, account, project, chat)).fetchone()
    if not b:
        raise ValueError(f'Unknown branch {branch_id!r} for this account/project/chat')
    if status == 'rejected':
        return reject_branch(con, account=account, project=project, chat=chat, branch_id=branch_id,
                             note=note, strategy_failure=strategy_failure, threshold=threshold, usage_status=usage_status)
    authority = 'user_direct' if decision_path == 'direct' else 'user_ratified_recommendation' if decision_path == 'accepted_recommendation' else 'system_process'
    append_event(con, account=account, project=project, chat=chat, event_type=f'branch.{status}', provenance='user' if decision_path != 'system' else 'system',
                 authority=authority, inference_kind='decision', truth_status='not_applicable', content=note or f'Branch {status}',
                 branch_id=branch_id, strategy_key=b['strategy_key'], metadata={'decision_path': decision_path})
    return None



def branch_usage_statuses(con, account: str, project: str, chat: str) -> dict[str, str]:
    """Current use label for rejected alternatives, derived from append-only events."""
    rows = con.execute("""SELECT branch_id,metadata_json FROM events WHERE account_id=? AND project_id=? AND chat_id=?
      AND event_type='branch.rejected' ORDER BY seq""", (account, project, chat)).fetchall()
    result = {}
    for row in rows:
        if row['branch_id']:
            meta = json.loads(row['metadata_json'] or '{}')
            result[row['branch_id']] = meta.get('usage_status', 'not_pertinent_now')
    return result

def gate_message(decision: str) -> dict:
    """Materiality gate. Ambiguity alone is not materiality; classification comes from caller."""
    messages = {
      'single': "Treating this as single-path; no material choice needs exposing. Say 'branch it' if you want options.",
      'clarify': "Low-cost ambiguity: I'll use context or ask one concise clarifying question, not expose a formal branch.",
      'branch': "Branching because this choice materially determines what happens next. Say 'just pick' to skip.",
      'recommend': "I'll recommend a branch with its material trade-off; you authorize before execution.",
      'just_pick': "Proceeding with a reasonable default, without branch exposure.",
      'branch_it': "Requested: rerun branch exposure from the original query."
    }
    if decision not in messages:
        raise ValueError(f'decision must be one of {sorted(messages)}')
    return {'decision': decision, 'message': messages[decision],
            'requires_user_authorization': decision in {'branch', 'recommend', 'branch_it'},
            'formal_branch_exposure': decision in {'branch', 'recommend', 'branch_it'}}


def _append_memory_event(con: sqlite3.Connection, *, memory_id: str, event_type: str,
                         from_state: str | None, to_state: str, from_stage: str | None,
                         to_stage: str, action_origin: str, note: str = '',
                         from_usage_status: str | None = None, to_usage_status: str | None = None) -> None:
    # Append a traceable memory lifecycle event; history rows are immutable.
    con.execute("""INSERT INTO memory_events(memory_id,occurred_at,event_type,from_state,to_state,from_stage,to_stage,from_usage_status,to_usage_status,action_origin,note)
      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
      (memory_id, now(), event_type, from_state, to_state, from_stage, to_stage, from_usage_status, to_usage_status, action_origin, note))
    con.commit()


def add_memory(con, *, account='default', scope: str, tag: str, claim: str,
               project: str | None = None, source_event_seq: int | None = None, weight: float = 1.0) -> str:
    # Store a candidate in a separate local-candidate table. It is not yet an
    # account/project memory and cannot be discovered by other runtime contexts.
    if scope not in {'account', 'project'}:
        raise ValueError('scope must be account or project')
    if scope == 'project' and not project:
        raise ValueError('project scope requires project_id')
    if not tag.strip() or not claim.strip():
        raise ValueError('tag and claim must be non-empty')
    if source_event_seq is None:
        raise ValueError('A source event is required so the proposed lesson remains traceable')
    source = con.execute('SELECT account_id,project_id,chat_id FROM events WHERE seq=?', (source_event_seq,)).fetchone()
    if not source:
        raise ValueError(f'Unknown source event sequence {source_event_seq}')
    if source['account_id'] != account:
        raise ValueError('Memory source event must belong to the same account')
    if scope == 'project' and source['project_id'] != project:
        raise ValueError('Project-scoped memory source event must belong to the same project')
    mid, ts = new_id('MEM'), now()
    con.execute('''INSERT INTO memory_candidates(candidate_id,account_id,scope,project_id,origin_project_id,chat_id,
      tag,claim,source_event_seq,state,usage_status,weight,created_at,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,'local_candidate','not_pertinent_now',?,?,?)''',
      (mid, account, scope, project, source['project_id'], source['chat_id'], tag, claim,
       source_event_seq, float(weight), ts, ts))
    con.commit()
    _append_memory_event(con, memory_id=mid, event_type='memory.proposed_local', from_state=None,
      to_state='local_candidate', from_stage=None, to_stage='local_candidate', action_origin='system',
      note=json.dumps({'claim': claim, 'source_event_seq': source_event_seq,
                       'scope': scope, 'project_id': project, 'origin_chat_id': source['chat_id']}, ensure_ascii=False),
      to_usage_status='not_pertinent_now')
    return mid


def review_memory_claim(con, memory_id: str, decision: str, *, edited_claim: str | None = None,
                        note: str = '') -> dict:
    # Accept/edit creates the shared read-only reference. Reject never creates a
    # shared memory row. The source claim and every choice remain in memory_events.
    row = con.execute('SELECT * FROM memory_candidates WHERE candidate_id=?', (memory_id,)).fetchone()
    if not row:
        raise ValueError(f'Unknown local memory candidate {memory_id}')
    if row['state'] != 'local_candidate':
        raise ValueError('Only a local candidate can undergo claim review')
    if decision not in {'accept', 'edit', 'reject'}:
        raise ValueError('decision must be accept, edit, or reject')
    old_claim = row['claim']
    ts = now()
    if decision == 'reject':
        con.execute("UPDATE memory_candidates SET state='rejected',updated_at=? WHERE candidate_id=?", (ts, memory_id))
        con.commit()
        _append_memory_event(con, memory_id=memory_id, event_type='memory.rejected_local',
          from_state='local_candidate', to_state='rejected', from_stage='local_candidate', to_stage='local_candidate',
          action_origin='user', note=json.dumps({'claim': old_claim, 'reason': note, 'data_retained_locally': True}, ensure_ascii=False),
          from_usage_status=row['usage_status'], to_usage_status=row['usage_status'])
        return {'memory_id': memory_id, 'decision': decision, 'stage': 'local_candidate', 'usage_status': row['usage_status'],
                'influence_permission': False, 'shared_memory_created': False, 'data_retained': True}
    if decision == 'edit':
        if edited_claim is None or not edited_claim.strip():
            raise ValueError('Edited claim text is required for decision=edit')
        new_claim = edited_claim.strip()
        event_type = 'memory.edited_and_pushed'
    else:
        if edited_claim is not None and edited_claim.strip() != old_claim:
            raise ValueError('Use decision=edit when changing the proposed claim')
        new_claim = old_claim
        event_type = 'memory.accepted_and_pushed'
    # Create the shared memory record only after explicit user acceptance/edit.
    con.execute('''INSERT INTO memories(memory_id,account_id,scope,project_id,tag,claim,source_event_seq,stage,usage_status,state,
      read_permission,influence_permission,weight,created_at,last_confirmed_at,updated_at)
      VALUES(?,?,?,?,?,?,?,'shared_reference',?,'pending',1,0,?,?,?,?)''',
      (memory_id, row['account_id'], row['scope'], row['project_id'], row['tag'], new_claim,
       row['source_event_seq'], row['usage_status'], row['weight'], ts, ts, ts))
    con.execute("UPDATE memory_candidates SET claim=?,state='pushed',updated_at=? WHERE candidate_id=?",
                (new_claim, ts, memory_id))
    con.commit()
    _append_memory_event(con, memory_id=memory_id, event_type=event_type,
      from_state='local_candidate', to_state='pending', from_stage='local_candidate', to_stage='shared_reference',
      action_origin='user', note=json.dumps({'prior_claim': old_claim, 'shared_claim': new_claim,
        'source_event_seq': row['source_event_seq'], 'note': note, 'data_retained': True}, ensure_ascii=False),
      from_usage_status=row['usage_status'], to_usage_status=row['usage_status'])
    return {'memory_id': memory_id, 'decision': decision, 'stage': 'shared_reference', 'usage_status': row['usage_status'],
            'claim': new_claim, 'influence_permission': False, 'shared_memory_created': True, 'data_retained': True}


def _resolution_target(decision: str) -> tuple[str, str, str, int, int, bool]:
    """Return stage, state, usage policy, read, influence, and legacy-alias flag."""
    aliases = {'keep': 'use', 'discard': 'not_pertinent_now'}
    legacy_alias = decision in aliases
    decision = aliases.get(decision, decision)
    mapping = {
        'use': ('keepable', 'active', 'use_when_relevant', 1, 1, legacy_alias),
        'avoid': ('keepable', 'active', 'never_try_again', 1, 1, legacy_alias),
        'later': ('shared_reference', 'pending', 'maybe_later', 1, 0, legacy_alias),
        'not_pertinent_now': ('shared_reference', 'pending', 'not_pertinent_now', 1, 0, legacy_alias),
    }
    if decision not in mapping:
        raise ValueError("decision must be use, avoid, later, or not_pertinent_now (legacy keep/discard are mapped without deleting data)")
    return mapping[decision]


def resolve_memory_reference(con, memory_id: str, decision: str, note: str = '') -> dict:
    """Set use policy for a shared read-only reference. Every outcome retains the record."""
    row = con.execute('SELECT * FROM memories WHERE memory_id=?', (memory_id,)).fetchone()
    if not row:
        raise ValueError(f'Unknown shared memory reference {memory_id}')
    if row['stage'] != 'shared_reference':
        raise ValueError('Only a shared read-only reference can be resolved here')
    stage, state, usage_status, read_perm, influence_perm, legacy_alias = _resolution_target(decision)
    ts = now()
    con.execute("""UPDATE memories SET stage=?,state=?,usage_status=?,read_permission=?,influence_permission=?,
      last_confirmed_at=CASE WHEN ? IN ('use','avoid','keep') THEN ? ELSE last_confirmed_at END,updated_at=? WHERE memory_id=?""",
      (stage, state, usage_status, read_perm, influence_perm, decision, ts, ts, memory_id))
    con.commit()
    normalized = {'use': 'use', 'keep': 'use', 'avoid': 'avoid', 'later': 'later',
                  'not_pertinent_now': 'not_pertinent_now', 'discard': 'not_pertinent_now'}.get(decision, decision)
    event_types = {'use': 'memory.marked_useful', 'avoid': 'memory.marked_do_not_repeat',
                   'later': 'memory.deferred', 'not_pertinent_now': 'memory.marked_not_pertinent_now'}
    _append_memory_event(con, memory_id=memory_id, event_type=event_types[normalized],
      from_state=row['state'], to_state=state, from_stage=row['stage'], to_stage=stage,
      action_origin='user', note=json.dumps({'decision': normalized, 'legacy_alias_used': legacy_alias,
        'claim_retained': True, 'note': note}, ensure_ascii=False),
      from_usage_status=row['usage_status'], to_usage_status=usage_status)
    return {'memory_id': memory_id, 'decision': normalized, 'stage': stage, 'state': state,
            'usage_status': usage_status, 'read_permission': bool(read_perm),
            'influence_permission': bool(influence_perm), 'data_retained': True,
            'legacy_alias_used': legacy_alias}


def resolve_memory_batch(con, memory_ids: list[str], decision: str, note: str = '') -> list[dict]:
    """Atomically assign a usage policy to references; none of the outcomes deletes data."""
    if not memory_ids or len(set(memory_ids)) != len(memory_ids):
        raise ValueError('Provide a non-empty list of unique memory IDs')
    stage, state, usage_status, read_perm, influence_perm, legacy_alias = _resolution_target(decision)
    rows = []
    for memory_id in memory_ids:
        row = con.execute('SELECT * FROM memories WHERE memory_id=?', (memory_id,)).fetchone()
        if not row:
            raise ValueError(f'Unknown shared memory reference {memory_id}; no batch items were changed')
        if row['stage'] != 'shared_reference':
            raise ValueError(f'Memory {memory_id} is not a shared read-only reference; no batch items were changed')
        rows.append(dict(row))
    normalized = {'use': 'use', 'keep': 'use', 'avoid': 'avoid', 'later': 'later',
                  'not_pertinent_now': 'not_pertinent_now', 'discard': 'not_pertinent_now'}.get(decision, decision)
    event_types = {'use': 'memory.marked_useful_in_batch', 'avoid': 'memory.marked_do_not_repeat_in_batch',
                   'later': 'memory.deferred_in_batch', 'not_pertinent_now': 'memory.marked_not_pertinent_now_in_batch'}
    ts, result = now(), []
    con.execute('SAVEPOINT memory_resolution_batch')
    try:
        for row in rows:
            last_confirmed = ts if normalized in {'use', 'avoid'} else row['last_confirmed_at']
            con.execute("""UPDATE memories SET stage=?,state=?,usage_status=?,read_permission=?,influence_permission=?,last_confirmed_at=?,updated_at=?
              WHERE memory_id=?""", (stage, state, usage_status, read_perm, influence_perm, last_confirmed, ts, row['memory_id']))
            con.execute("""INSERT INTO memory_events(memory_id,occurred_at,event_type,from_state,to_state,from_stage,to_stage,
              from_usage_status,to_usage_status,action_origin,note) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (row['memory_id'], ts, event_types[normalized], row['state'], state, row['stage'], stage,
               row['usage_status'], usage_status, 'user', json.dumps({'decision': normalized, 'note': note,
               'claim_retained': True, 'legacy_alias_used': legacy_alias}, ensure_ascii=False)))
            result.append({'memory_id': row['memory_id'], 'decision': normalized, 'stage': stage, 'state': state,
                           'usage_status': usage_status, 'influence_permission': bool(influence_perm), 'data_retained': True})
        con.execute('RELEASE SAVEPOINT memory_resolution_batch'); con.commit()
    except Exception:
        con.execute('ROLLBACK TO SAVEPOINT memory_resolution_batch'); con.execute('RELEASE SAVEPOINT memory_resolution_batch'); con.rollback(); raise
    return result


def set_memory_usage_status(con, memory_id: str, usage_status: str, note: str = '') -> dict:
    """Change use policy without deleting the memory or rewriting its origin."""
    if usage_status not in VALID_USAGE_STATUSES:
        raise ValueError(f'usage_status must be one of {sorted(VALID_USAGE_STATUSES)}')
    row = con.execute('SELECT * FROM memories WHERE memory_id=?', (memory_id,)).fetchone()
    if not row:
        # Local candidates remain local; a usage tag does not implicitly share them.
        cand = con.execute('SELECT * FROM memory_candidates WHERE candidate_id=?', (memory_id,)).fetchone()
        if not cand:
            raise ValueError(f'Unknown memory {memory_id}')
        con.execute('UPDATE memory_candidates SET usage_status=?,updated_at=? WHERE candidate_id=?', (usage_status, now(), memory_id))
        con.commit()
        _append_memory_event(con, memory_id=memory_id, event_type='memory.local_usage_status_changed',
          from_state=cand['state'], to_state=cand['state'], from_stage=cand['state'], to_stage=cand['state'],
          action_origin='user', note=json.dumps({'note': note, 'data_retained_locally': True}, ensure_ascii=False),
          from_usage_status=cand['usage_status'], to_usage_status=usage_status)
        return {'memory_id': memory_id, 'usage_status': usage_status, 'shared': False,
                'influence_permission': False, 'data_retained': True}

    if row['state'] == 'reversed' and usage_status in {'use_when_relevant', 'never_try_again'}:
        raise ValueError('An explicitly reversed memory requires an explicit reactivate action before active use.')
    active_use = usage_status in {'use_when_relevant', 'never_try_again'}
    stage = 'keepable' if active_use else row['stage']
    state = row['state']
    if row['stage'] == 'shared_reference' and active_use:
        # An explicit usage decision is also the user's ratification of this reference.
        state = 'active'
    influence = int(active_use and state == 'active')
    ts = now()
    con.execute("""UPDATE memories SET stage=?,state=?,usage_status=?,read_permission=1,influence_permission=?,last_confirmed_at=CASE WHEN ?=1 THEN ? ELSE last_confirmed_at END,updated_at=? WHERE memory_id=?""",
      (stage, state, usage_status, influence, influence, ts, ts, memory_id))
    con.commit()
    _append_memory_event(con, memory_id=memory_id, event_type='memory.usage_status_changed',
      from_state=row['state'], to_state=state, from_stage=row['stage'], to_stage=stage,
      action_origin='user', note=json.dumps({'note': note, 'data_retained': True}, ensure_ascii=False),
      from_usage_status=row['usage_status'], to_usage_status=usage_status)
    return {'memory_id': memory_id, 'usage_status': usage_status, 'stage': stage, 'state': state,
            'influence_permission': bool(influence), 'data_retained': True}

def change_memory_state(con, memory_id: str, action: str, note: str = '') -> None:
    # Manage authority walk-back only after a memory has been explicitly kept.
    row = con.execute('SELECT * FROM memories WHERE memory_id=?', (memory_id,)).fetchone()
    if not row:
        raise ValueError(f'Unknown memory {memory_id}')
    if action == 'ratify':
        # Compatibility alias for the explicit second-stage keep decision.
        resolve_memory_reference(con, memory_id, 'keep', note=note)
        return
    if row['stage'] != 'keepable':
        raise ValueError('Only a kept memory can change active/dormant/reversed authority; review and keep it first')
    ts = now()
    transitions = {
      'dormant': ('dormant', 1, 0),
      'reverse': ('reversed', 1, 0),
      'reactivate': ('active', 1, 1),
      'confirm': ('active', 1, 1)
    }
    if action not in transitions:
        raise ValueError(f'action must be one of {sorted(transitions)}')
    if row['state'] == 'reversed' and action == 'confirm':
        raise ValueError('An explicit reversal cannot be undone by ordinary confirmation; use explicit reactivate.')
    state, can_read, can_influence = transitions[action]
    last_confirmed = ts if action in {'reactivate','confirm'} else row['last_confirmed_at']
    con.execute('UPDATE memories SET state=?,read_permission=?,influence_permission=?,last_confirmed_at=?,updated_at=? WHERE memory_id=?',
                (state, can_read, can_influence, last_confirmed, ts, memory_id))
    con.commit()
    _append_memory_event(con, memory_id=memory_id, event_type=f'memory.{action}', from_state=row['state'],
      to_state=state, from_stage=row['stage'], to_stage=row['stage'],
      action_origin='user' if action in {'reverse','reactivate'} else 'system', note=note)



def reopen_memory_candidate(con, memory_id: str, note: str = '') -> dict:
    """Reopen a previously declined local proposal without copying it to shared context."""
    row = con.execute('SELECT * FROM memory_candidates WHERE candidate_id=?', (memory_id,)).fetchone()
    if not row:
        raise ValueError(f'Unknown local memory candidate {memory_id}')
    if row['state'] != 'rejected':
        raise ValueError('Only a locally rejected candidate can be reopened')
    con.execute("UPDATE memory_candidates SET state='local_candidate',updated_at=? WHERE candidate_id=?", (now(), memory_id))
    con.commit()
    _append_memory_event(con, memory_id=memory_id, event_type='memory.local_candidate_reopened',
      from_state='rejected', to_state='local_candidate', from_stage='local_candidate', to_stage='local_candidate',
      action_origin='user', note=json.dumps({'note': note, 'claim_retained': True}, ensure_ascii=False),
      from_usage_status=row['usage_status'], to_usage_status=row['usage_status'])
    return {'memory_id': memory_id, 'state': 'local_candidate', 'usage_status': row['usage_status'],
            'shared': False, 'influence_permission': False, 'data_retained': True}

def list_memories(con, *, account='default', project: str | None = None, tag: str | None = None,
                  include_local: bool = False, include_discarded: bool = False) -> list[dict]:
    """List retained records and their use status. Legacy discarded rows remain inspectable."""
    sql = 'SELECT * FROM memories WHERE account_id=?'
    args: list[Any] = [account]
    if project is not None:
        sql += " AND (scope='account' OR (scope='project' AND project_id=?))"
        args.append(project)
    if tag:
        sql += ' AND tag=?'; args.append(tag)
    stages = ['shared_reference', 'keepable']
    if include_discarded:  # compatibility for older databases; no new path uses this stage
        stages.append('discarded')
    sql += ' AND stage IN (' + ','.join('?' for _ in stages) + ')'
    args.extend(stages)
    sql += ' ORDER BY created_at'
    memories = [dict(r) for r in con.execute(sql, args).fetchall()]
    if include_local:
        csql = 'SELECT * FROM memory_candidates WHERE account_id=?'
        cargs: list[Any] = [account]
        if project is not None:
            csql += " AND (scope='account' OR (scope='project' AND project_id=?))"
            cargs.append(project)
        if tag:
            csql += ' AND tag=?'; cargs.append(tag)
        csql += ' ORDER BY created_at'
        for candidate in con.execute(csql, cargs).fetchall():
            item = dict(candidate)
            item.update({'memory_id': item['candidate_id'], 'stage': 'local_candidate' if item['state'] in {'local_candidate','rejected'} else 'promoted_from_local',
                         'read_permission': 0, 'influence_permission': 0, 'shared': False})
            memories.append(item)
    return sorted(memories, key=lambda m: m['created_at'])

def revision_statuses_for_scope(con, account: str, project: str, chat: str) -> dict[str, str]:
    result: dict[str, str] = {}
    rows = con.execute('''SELECT p.proposal_id, e.to_state FROM revision_proposals p
      JOIN revision_events e ON e.proposal_id=p.proposal_id
      WHERE p.account_id=? AND p.project_id=? AND p.chat_id=?
      AND e.seq=(SELECT MAX(e2.seq) FROM revision_events e2 WHERE e2.proposal_id=p.proposal_id)''',
      (account, project, chat)).fetchall()
    for row in rows:
        result[row['proposal_id']] = row['to_state']
    return result


def context_projection(con, *, account='default', project: str, chat: str, recent_assistant_turns: int = 6,
                       relevance_tags: set[str] | None = None) -> dict:
    """Build a fresh context projection. History is immutable; this is not the canonical record."""
    events = scope_events(con, account, project, chat)
    statuses = branch_statuses(con, account, project, chat)
    revision_statuses = revision_statuses_for_scope(con, account, project, chat)
    # Only the most recent N assistant outputs remain active. Old assistant turns remain in history verbatim.
    assistant_seqs = [e['seq'] for e in events if e['provenance'] == 'assistant'
                      and not (e['branch_id'] and statuses.get(e['branch_id']) == 'rejected')]
    recent_assistant = set(assistant_seqs[-recent_assistant_turns:]) if recent_assistant_turns else set()
    active, excluded = [], []
    for e in events:
        rejected = bool(e['branch_id'] and statuses.get(e['branch_id']) == 'rejected')
        stale_ai = e['provenance'] == 'assistant' and e['seq'] not in recent_assistant
        event_meta = json.loads(e.get('metadata_json') or '{}')
        revision_id = event_meta.get('proposal_id')
        revision_state = revision_statuses.get(revision_id) if revision_id else None
        superseded_revision_acceptance = (e['event_type'] == 'revision.accepted' and revision_state not in {'accepted_for_expansion', 'expanded'})
        if superseded_revision_acceptance:
            e['projection_status'] = 'superseded_acceptance_retained_in_history'
            excluded.append(e)
        elif rejected and e['event_type'] != 'branch.rejected':
            e['projection_status'] = 'zero_weight_rejected_branch'
            excluded.append(e)
        elif stale_ai:
            e['projection_status'] = 'historical_artifact_not_active_by_default'
            excluded.append(e)
        else:
            e['projection_status'] = 'active'
            active.append(e)
    memories = list_memories(con, account=account, project=project)
    readable = [m for m in memories if m['read_permission'] and m.get('stage') in {'shared_reference', 'keepable'}]
    def can_influence(m):
        if not (m['stage'] == 'keepable' and m['state'] == 'active' and m['influence_permission']):
            return False
        usage = m.get('usage_status', 'use_when_relevant')
        if usage not in {'use_when_relevant', 'never_try_again'}:
            return False
        if usage == 'never_try_again':
            # Avoidance rules are conditional: inject only on explicit tag/strategy match.
            return relevance_tags is not None and m['tag'] in relevance_tags
        # With no explicit relevance signal, retain the memory but do not assume it applies.
        # The reserved tag 'always' is an explicit opt-in to cross-task influence.
        return m['tag'] == 'always' or (relevance_tags is not None and m['tag'] in relevance_tags)
    influencing = [m for m in readable if can_influence(m)]
    influencing_ids = {m['memory_id'] for m in influencing}
    # References are queryable but deliberately not injected as instructions or active context.
    read_only_references = [m for m in readable if m['memory_id'] not in influencing_ids]
    return {
      'schema_version': 2, 'account_id': account, 'project_id': project, 'chat_id': chat,
      'hydrated_at': now(), 'last_event_seq': max((e['seq'] for e in events), default=0),
      'active_events': active, 'excluded_from_active_context': excluded,
      'branch_statuses': statuses, 'branch_usage_statuses': branch_usage_statuses(con, account, project, chat),
      'revision_statuses': revision_statuses,
      'relevance_tags': sorted(relevance_tags) if relevance_tags is not None else None,
      'memories_influencing_context': influencing,
      'read_only_memory_references': read_only_references, 'history_event_count': len(events), 'immutable_history_available': True,
      'notes': [
        'History is authoritative; active context is a disposable projection.',
        'Rejected branch output remains in history; its current-use disposition is recorded separately.',
        'Information can remain stored while marked not pertinent now or maybe later; status controls use, not retention.',
        'Old assistant turns are retained verbatim as history and are not silently summarized into active context.',
        'User-originated active events are retained verbatim by the model-context packer; protected overflow fails closed rather than truncating them.',
        'Non-ratified/dormant/reversed memories are queryable references, not automatic instructions in active context.'
      ]
    }


def render_markdown(payload: dict) -> str:
    lines = [f"# AEL Context Projection — {payload['project_id']} / {payload['chat_id']}", '',
             f"- Account: `{payload['account_id']}`", f"- Hydrated: {payload['hydrated_at']}",
             f"- Last event sequence: {payload['last_event_seq']}", f"- Historical events: {payload['history_event_count']}",
             '- Canonical record: persistent event ledger; this projection is disposable.', '']
    lines += ['## Active context', '']
    if not payload['active_events']:
        lines.append('_No active events recorded._')
    for e in payload['active_events']:
        lines += [f"### #{e['seq']} · {e['event_type']} · provenance: {e['provenance']}",
                  f"- Authority: `{e['authority']}` · inference kind: `{e['inference_kind']}` · truth status: `{e['truth_status']}`",
                  f"- Event ID: `{e['event_id']}` · Source ref: `{e['source_ref'] or 'not supplied'}`"]
        if e['branch_id']:
            lines.append(f"- Branch: `{e['branch_id']}`")
        lines += ['', e['content'], '']
    lines += ['## Branch ledger', '']
    branches = [dict(r) for r in []]
    # Statuses are projected from append-only decision events.
    branch_rows = payload.get('branches', [])
    if not branch_rows:
        lines.append('_No branches recorded._')
    for b in branch_rows:
        status = payload['branch_statuses'].get(b['branch_id'], 'proposed')
        if status == 'rejected':
            # Do not put rejected strategy wording or trade-offs back into the prompt-facing projection.
            usage = payload.get('branch_usage_statuses', {}).get(b['branch_id'], 'not_pertinent_now')
            lines.append(f"- `{b['branch_id']}` — **rejected for this attempt; usage={usage}; output retained in history, not active context**")
        else:
            lines.append(f"- `{b['branch_id']}` — **{status}** — {b['label']} — trade-off: {b['tradeoff']}")
    lines += ['', '## Memory influencing this context', '']
    if not payload['memories_influencing_context']:
        lines.append('_No ratified memory is currently influencing this context._')
    for m in payload['memories_influencing_context']:
        label = 'AVOID STRATEGY' if m.get('usage_status') == 'never_try_again' else 'USE WHEN RELEVANT'
        lines.append(f"- [{label} | {m['scope']}:{m['tag']}] {m['claim']} (weight={m['weight']}; source_event_seq={m['source_event_seq']})")
    lines += ['', '## Read-only memory references', '']
    ref_count = len(payload.get('read_only_memory_references', []))
    if ref_count:
        lines.append(f'{ref_count} reference(s) are available for explicit retrieval from the memory store; their claims are not injected into this context.')
    else:
        lines.append('_No read-only references available._')
    lines += ['', '## Excluded from active context but retained in history', '']
    if not payload['excluded_from_active_context']:
        lines.append('_None._')
    for e in payload['excluded_from_active_context']:
        digest = hashlib.sha256(e['content'].encode('utf-8')).hexdigest()[:12]
        lines.append(f"- Event #{e['seq']} `{e['event_type']}`: {e['projection_status']} — content retained in ledger only (sha256:{digest})")
    lines += ['', '## Recovery instruction', '',
      'Rebuild active context from the stable ledger. Do not reintroduce rejected branch artifacts unless the user explicitly asks to reconsider them. Inspect source references before treating an inference or generated artifact as verified fact.', '']
    return '\n'.join(lines)


def hydrate_payload(con, *, account='default', project: str, chat: str, recent_assistant_turns: int = 6,
                    relevance_tags: set[str] | None = None) -> dict:
    payload = context_projection(con, account=account, project=project, chat=chat,
                                 recent_assistant_turns=recent_assistant_turns, relevance_tags=relevance_tags)
    payload['branches'] = [dict(r) for r in con.execute('''SELECT * FROM branches WHERE account_id=? AND project_id=? AND chat_id=? ORDER BY proposed_at''',
                                                        (account, project, chat)).fetchall()]
    return payload


class ProtectedContextOverflow(RuntimeError):
    """Raised when protected, unabridged content cannot fit the requested context budget."""

    def __init__(self, *, budget: int, required: int, protected_event_seqs: list[int], protected_memory_ids: list[str]):
        self.budget = budget
        self.required = required
        self.protected_event_seqs = protected_event_seqs
        self.protected_memory_ids = protected_memory_ids
        super().__init__(
            f"Protected context needs about {required} token-units but budget is {budget}. "
            "No partial context was emitted; increase the budget or explicitly choose a smaller source scope."
        )


def rough_token_estimate(text: str) -> int:
    """Portable fallback estimate, not a provider tokenizer. Adapters should inject an exact counter."""
    if not text:
        return 0
    # A crude UTF-8-byte estimate intentionally kept behind a replaceable callable.
    # It is not guaranteed to upper-bound any provider's tokenization.
    return max(1, ceil(len(text.encode('utf-8')) / 3))


def _event_priority(event: dict) -> int:
    """Deterministic selection priority for non-protected events; not a truth/confidence score."""
    event_type = event.get('event_type', '')
    if event_type in {'branch.proposed', 'branch.selected', 'branch.completed', 'materiality_gate.assessed', 'materiality_gate.override'}:
        return 90
    if event_type in {'evidence', 'external_evidence', 'tool_result', 'verified_result'}:
        return 80
    if event_type in {'observation', 'hypothesis', 'active_frame', 'handoff_note', 'test_result'}:
        return 70
    if event.get('provenance') == 'external':
        return 60
    if event.get('provenance') == 'system':
        return 50
    if event.get('provenance') == 'assistant':
        return 10
    return 40


def _format_context_event(event: dict) -> str:
    source = event.get('source_ref') or 'not supplied'
    branch = f"; branch={event['branch_id']}" if event.get('branch_id') else ''
    meta = json.loads(event.get('metadata_json') or '{}')
    usage = f"; usage_policy={meta.get('usage_status')}" if event.get('event_type') == 'branch.rejected' else ''
    return (
        f"[event #{event['seq']} | type={event['event_type']} | provenance={event['provenance']}"
        f" | authority={event['authority']} | inference={event['inference_kind']}"
        f" | truth_status={event['truth_status']} | source={source}{branch}{usage}]\n"
        f"{event['content']}"
    )


def render_model_context(
    payload: dict,
    *,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
) -> dict:
    """Build a bounded model-facing context from ACTIVE projection only.

    This function never compresses or truncates event text. Active user-originated
    events and ratified influential memories are mandatory. If mandatory material
    does not fit, it fails closed. Lower-priority complete events may be omitted,
    and their IDs are returned in a sidecar report (not with their content).

    `token_counter` should be supplied by a future model adapter. The default is a
    documented rough estimate for offline testing, not an exact token count.
    Only `context_text` is intended for model input; do not send the full audit payload.
    """
    if max_tokens <= 0:
        raise ValueError('max_tokens must be positive')
    count = token_counter or rough_token_estimate
    active_events = list(payload.get('active_events', []))
    influencing = list(payload.get('memories_influencing_context', []))

    # User-originated turns remain verbatim. Runtime decision records and explicit
    # constraints are protected even if their provenance was assigned by a wrapper.
    protected_types = {'initial_brief', 'constraint', 'original_query', 'user_correction', 'branch.rejected'}
    protected_events = [e for e in active_events if e.get('provenance') == 'user' or e.get('event_type') in protected_types]
    protected_ids = {e['seq'] for e in protected_events}

    def render(events: list[dict]) -> str:
        lines = [
            '# Active AEL working context',
            f"Account: {payload.get('account_id', 'default')}",
            f"Project: {payload.get('project_id', '')}",
            f"Chat: {payload.get('chat_id', '')}",
            f"Ledger position: event #{payload.get('last_event_seq', 0)}; historical event count: {payload.get('history_event_count', 0)}",
            'This is a bounded projection, not the canonical history. Included user events are verbatim. Rejected alternatives and non-pertinent/deferred memories remain stored but are not injected; absence from this projection is not deletion.',
            '',
        ]
        if influencing:
            lines.extend(['## Ratified memories permitted to influence this context', ''])
            for mem in influencing:
                prefix = 'AVOID STRATEGY' if mem.get('usage_status') == 'never_try_again' else 'USE WHEN RELEVANT'
                lines.append(f"- [{prefix} | {mem['scope']}:{mem['tag']}] {mem['claim']} (memory_id={mem['memory_id']}; source_event_seq={mem.get('source_event_seq')})")
            lines.append('')
        lines.extend(['## Active events', ''])
        for event in sorted(events, key=lambda e: e['seq']):
            lines.append(_format_context_event(event))
            lines.append('')
        return '\n'.join(lines).rstrip() + '\n'

    selected = list(protected_events)
    baseline_text = render(selected)
    baseline_tokens = count(baseline_text)
    protected_memory_ids = [m['memory_id'] for m in influencing]
    if baseline_tokens > max_tokens:
        raise ProtectedContextOverflow(
            budget=max_tokens,
            required=baseline_tokens,
            protected_event_seqs=sorted(protected_ids),
            protected_memory_ids=protected_memory_ids,
        )

    candidates = [e for e in active_events if e['seq'] not in protected_ids]
    # Priority first, then most recent within a priority. Every item is atomic:
    # no sentence or event is cut mid-way to make a budget fit.
    candidates.sort(key=lambda e: (_event_priority(e), e['seq']), reverse=True)
    selected_ids = set(protected_ids)
    omitted = []
    for event in candidates:
        trial = selected + [event]
        trial_text = render(trial)
        trial_tokens = count(trial_text)
        if trial_tokens <= max_tokens:
            selected = trial
            selected_ids.add(event['seq'])
        else:
            omitted.append({
                'seq': event['seq'],
                'event_type': event['event_type'],
                'provenance': event['provenance'],
                'reason': 'whole_event_did_not_fit',
                'retrieval_hint': f"Retrieve historical event #{event['seq']} explicitly if needed.",
            })

    text = render(selected)
    estimated = count(text)
    if estimated > max_tokens:
        # Defensive invariant: fail closed rather than emitting an over-budget pack.
        raise RuntimeError(f'Context packing invariant failed: {estimated} > {max_tokens}')
    return {
        'schema_version': 1,
        'account_id': payload.get('account_id'),
        'project_id': payload.get('project_id'),
        'chat_id': payload.get('chat_id'),
        'last_event_seq': payload.get('last_event_seq', 0),
        'context_text': text,
        'budget': {
            'max_tokens': max_tokens,
            'estimated_tokens': estimated,
            'counter': 'injected_provider_counter' if token_counter else 'rough_utf8_estimate_not_provider_exact',
            'fits_estimated_budget': estimated <= max_tokens,
        },
        'included_event_seqs': sorted(selected_ids),
        'protected_event_seqs': sorted(protected_ids),
        'omitted_events': omitted,
        'influencing_memory_ids': protected_memory_ids,
        'read_only_memory_ids_not_injected': [m['memory_id'] for m in payload.get('read_only_memory_references', [])],
        'source_policy': 'No content is truncated or summarized. Omitted non-protected event IDs remain retrievable from canonical history.',
    }


def build_model_input(
    payload: dict,
    current_user_message: str,
    *,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
    reserved_tokens: int = 0,
) -> tuple[dict, dict]:
    """Build the strictly allowlisted model input and a separate audit sidecar.

    The returned request contains only the bounded active context and the current
    user message. History, exclusions, event lists, memory references, hashes and
    diagnostics are returned separately and must never be serialized to a model.
    This is a provider-neutral input envelope, not a provider adapter.
    """
    if not isinstance(current_user_message, str) or not current_user_message.strip():
        raise ValueError('current_user_message must be non-empty')
    if reserved_tokens < 0 or reserved_tokens >= max_tokens:
        raise ValueError('reserved_tokens must be non-negative and smaller than max_tokens')
    context_budget = max_tokens - reserved_tokens
    packed = render_model_context(payload, max_tokens=context_budget, token_counter=token_counter)
    model_input = {
        'working_context': packed['context_text'],
        'current_user_message': current_user_message,
    }
    audit = {
        'schema_version': 1,
        'account_id': packed.get('account_id'),
        'project_id': packed.get('project_id'),
        'chat_id': packed.get('chat_id'),
        'last_event_seq': packed.get('last_event_seq'),
        'context_sha256': hashlib.sha256(packed['context_text'].encode('utf-8')).hexdigest(),
        'included_event_seqs': packed['included_event_seqs'],
        'protected_event_seqs': packed['protected_event_seqs'],
        'omitted_events': packed['omitted_events'],
        'influencing_memory_ids': packed['influencing_memory_ids'],
        'read_only_memory_ids_not_injected': packed['read_only_memory_ids_not_injected'],
        'context_packing': packed['budget'],
        'source_policy': packed['source_policy'],
        'model_input_keys': sorted(model_input.keys()),
        'budget': {'total_input_budget': max_tokens, 'reserved_for_prompt_and_current_message': reserved_tokens,
                   'working_context_budget': context_budget, 'counter': packed['budget']['counter']},
        'rule': 'Only model_input may be sent to a provider. The audit sidecar is runtime-only.',
    }
    return model_input, audit


def _validate_loopback_ollama_origin(base_url: str):
    """Accept only a bare HTTP loopback origin; never send context to a remote host."""
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('Only an HTTP loopback Ollama endpoint is allowed; remote hosts are refused by default')
    if parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise ValueError('base_url must be a bare loopback origin such as http://127.0.0.1:11434')
    return parsed


def ollama_status(base_url: str = 'http://127.0.0.1:11434', timeout: float = 3.0) -> dict[str, Any]:
    """Check the local Ollama tag endpoint without sending a prompt or using a token."""
    parsed = _validate_loopback_ollama_origin(base_url)
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    request = urllib.request.Request(base_url.rstrip('/') + '/api/tags', method='GET')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': f'Local Ollama returned HTTP {exc.code}'}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': 'Ollama is not reachable at this loopback endpoint'}
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': 'Ollama returned invalid JSON from /api/tags'}
    rows = body.get('models')
    if not isinstance(rows, list):
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': 'Ollama /api/tags response has no models list'}
    names = sorted({row.get('name') for row in rows if isinstance(row, dict) and isinstance(row.get('name'), str)})
    local_names = [name for name in names if not name.casefold().endswith(':cloud')]
    cloud_names = [name for name in names if name.casefold().endswith(':cloud')]
    return {'available': True, 'endpoint_host': parsed.hostname, 'models': names,
            'local_models': local_names, 'cloud_models_excluded': cloud_names, 'api_token_used': False}


OLLAMA_SYSTEM_PROMPT = (
    'You are responding through an AEL-governed local runtime. The user message contains a bounded '
    'working-context projection followed by the current request. The projection is not the complete '
    'historical record. Preserve explicit user constraints and decisions; distinguish source provenance, '
    'decision authority, factual truth, and AI inference. Do not claim access to omitted history, and do '
    'not treat earlier AI-generated text as independent evidence.'
)


def ollama_chat(model_input: dict, *, model: str, base_url: str = 'http://127.0.0.1:11434',
                timeout: float = 120.0) -> dict:
    """Call a loopback-only Ollama chat endpoint using only the allowlisted model input.

    No API token is used. The default endpoint is local. Remote hosts are refused to
    avoid silently sending the user's context to a network service. Uses Ollama's
    non-streaming POST /api/chat response shape.
    """
    if set(model_input.keys()) != {'working_context', 'current_user_message'}:
        raise ValueError('model_input must contain exactly working_context and current_user_message')
    if not isinstance(model_input['working_context'], str):
        raise ValueError('working_context must be text')
    if not isinstance(model_input['current_user_message'], str) or not model_input['current_user_message'].strip():
        raise ValueError('current_user_message must be non-empty text')
    if not isinstance(model, str) or not model.strip():
        raise ValueError('model must be a non-empty local model name')
    if model.strip().casefold().endswith(':cloud'):
        raise ValueError('Cloud model names are not permitted in the local-only AEL bridge; choose a model downloaded to this computer')
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    parsed = _validate_loopback_ollama_origin(base_url)
    endpoint = base_url.rstrip('/') + '/api/chat'
    combined_user_content = (
        '=== BOUNDED WORKING CONTEXT (reference material; not the complete history) ===\n'
        + model_input['working_context']
        + '\n\n=== CURRENT USER MESSAGE ===\n'
        + model_input['current_user_message']
    )
    request_body = {
        'model': model.strip(),
        'messages': [
            {'role': 'system', 'content': OLLAMA_SYSTEM_PROMPT},
            {'role': 'user', 'content': combined_user_content},
        ],
        'stream': False,
    }
    raw = json.dumps(request_body, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(endpoint, data=raw, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_text = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Local Ollama returned HTTP {exc.code}; check the local service and model name') from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError('Could not reach the local Ollama endpoint. Confirm Ollama is running at the configured loopback address.') from exc
    try:
        body = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Local Ollama returned invalid JSON; streaming may be enabled unexpectedly') from exc
    message = body.get('message')
    if not isinstance(message, dict) or not isinstance(message.get('content'), str):
        raise RuntimeError('Local Ollama response did not contain message.content text')
    metrics = {key: body[key] for key in ('total_duration', 'load_duration', 'prompt_eval_count', 'eval_count') if key in body}
    return {
        'provider': 'ollama-local',
        'model': body.get('model', model.strip()),
        'content': message['content'],
        'done': bool(body.get('done', True)),
        'metrics': metrics,
        'endpoint_host': parsed.hostname,
        'request_fields': sorted(request_body.keys()),
        'sent_streaming': False,
        'api_token_used': False,
    }


@dataclass
class LocalContext:
    account_id: str
    project_id: str
    chat_id: str
    payload: dict
    runtime_instance_id: str


class RuntimeSession:
    """One active chat -> one disposable LocalContext. Switching chat forces hydration anew."""
    def __init__(self, con: sqlite3.Connection, account='default'):
        self.con, self.account_id = con, account
        self.local_context: LocalContext | None = None
        self.lifecycle_log: list[str] = []

    def open_chat(self, project: str, chat: str) -> LocalContext:
        if self.local_context and (self.local_context.project_id != project or self.local_context.chat_id != chat):
            old = self.local_context
            self.lifecycle_log.append(f'destroyed:{old.project_id}/{old.chat_id}:{old.runtime_instance_id}')
            self.local_context = None
        if self.local_context is None:
            payload = hydrate_payload(self.con, account=self.account_id, project=project, chat=chat)
            self.local_context = LocalContext(self.account_id, project, chat, payload, new_id('CTX'))
            self.lifecycle_log.append(f'hydrated:{project}/{chat}:{self.local_context.runtime_instance_id}')
        else:
            self.refresh_in_place()
        return self.local_context

    def refresh_in_place(self) -> LocalContext:
        if self.local_context is None:
            raise RuntimeError('No active chat to refresh')
        c = self.local_context
        c.payload = hydrate_payload(self.con, account=self.account_id, project=c.project_id, chat=c.chat_id)
        self.lifecycle_log.append(f'refreshed:{c.project_id}/{c.chat_id}:{c.runtime_instance_id}')
        return c

    def pivot_with_reset(self, branch_id: str, note: str, strategy_failure=False, threshold=3) -> dict:
        if self.local_context is None:
            raise RuntimeError('No active chat to pivot')
        c = self.local_context
        outcome = decide_branch(self.con, account=c.account_id, project=c.project_id, chat=c.chat_id,
                                branch_id=branch_id, status='rejected', note=note,
                                strategy_failure=strategy_failure, threshold=threshold)
        oldid = c.runtime_instance_id
        self.local_context = None  # discard the dirty runtime object; do not ask the model to ignore text still present
        self.lifecycle_log.append(f'pivot-destroyed:{c.project_id}/{c.chat_id}:{oldid}')
        fresh = self.open_chat(c.project_id, c.chat_id)
        self.lifecycle_log.append(f'pivot-rehydrated:{fresh.project_id}/{fresh.chat_id}:{fresh.runtime_instance_id}')
        return outcome

    def reject_revision_with_reset(self, proposal_id: str, note: str) -> dict:
        if self.local_context is None:
            raise RuntimeError('No active chat to reset')
        c = self.local_context
        outcome = decide_revision(self.con, proposal_id, 'reject', note=note,
                                  account=c.account_id, project=c.project_id, chat=c.chat_id)
        oldid = c.runtime_instance_id
        self.local_context = None
        self.lifecycle_log.append(f'revision-reset-destroyed:{c.project_id}/{c.chat_id}:{oldid}')
        fresh = self.open_chat(c.project_id, c.chat_id)
        self.lifecycle_log.append(f'revision-reset-rehydrated:{fresh.project_id}/{fresh.chat_id}:{fresh.runtime_instance_id}')
        outcome['runtime_reset'] = True
        outcome['new_runtime_instance_id'] = fresh.runtime_instance_id
        return outcome


def checkpoint(con, *, account='default', project: str, chat: str, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    payload = hydrate_payload(con, account=account, project=project, chat=chat)
    md, js = out / f'checkpoint-{project}-{chat}.md', out / f'checkpoint-{project}-{chat}.json'
    md.write_text(render_markdown(payload), encoding='utf-8')
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    js.write_text(raw, encoding='utf-8')
    # Verify snapshot can be parsed and sequence/hash corresponds to ledger projection.
    saved_raw = js.read_text(encoding='utf-8')
    loaded = json.loads(saved_raw)
    if loaded['last_event_seq'] != payload['last_event_seq']:
        raise RuntimeError('Checkpoint event sequence verification failed')
    sha = hashlib.sha256(saved_raw.encode('utf-8')).hexdigest()
    con.execute('''INSERT INTO checkpoints(checkpoint_id,created_at,account_id,project_id,chat_id,last_event_seq,markdown_path,json_path,snapshot_sha256)
      VALUES(?,?,?,?,?,?,?,?,?)''', (new_id('CP'), now(), account, project, chat, payload['last_event_seq'], str(md), str(js), sha))
    con.commit()
    return md, js


def delta_preview(old_text: str, new_text: str, fromfile='current', tofile='proposed') -> dict:
    diff = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), fromfile=fromfile, tofile=tofile, lineterm=''))
    added = sum(1 for x in diff if x.startswith('+') and not x.startswith('+++'))
    removed = sum(1 for x in diff if x.startswith('-') and not x.startswith('---'))
    return {'added_lines': added, 'removed_lines': removed, 'diff': '\n'.join(diff),
            'requires_review_before_expansion': True}


REVISION_STATES = {'proposed', 'accepted_for_expansion', 'rejected', 'rejected_reset', 'expanded'}


def _revision_payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _get_revision(con, proposal_id: str, *, account: str | None = None,
                  project: str | None = None, chat: str | None = None) -> dict:
    clauses = ['proposal_id=?']
    args: list[Any] = [proposal_id]
    for col, val in (('account_id', account), ('project_id', project), ('chat_id', chat)):
        if val is not None:
            clauses.append(f'{col}=?')
            args.append(val)
    row = con.execute('SELECT * FROM revision_proposals WHERE ' + ' AND '.join(clauses), args).fetchone()
    if not row:
        raise ValueError(f'Unknown revision proposal {proposal_id!r} in this scope')
    result = dict(row)
    result['changed_sections'] = json.loads(result.pop('changed_sections_json'))
    return result


def _revision_state(con, proposal_id: str) -> str:
    row = con.execute('SELECT to_state FROM revision_events WHERE proposal_id=? ORDER BY seq DESC LIMIT 1',
                       (proposal_id,)).fetchone()
    if not row:
        raise RuntimeError(f'Revision {proposal_id} has no lifecycle event')
    return str(row['to_state'])


def _append_revision_event(con, *, proposal: dict, event_type: str, from_state: str | None,
                           to_state: str, action_origin: str, note: str = '',
                           metadata: dict | None = None) -> dict:
    if to_state not in REVISION_STATES:
        raise ValueError(f'Invalid revision state {to_state!r}')
    cur = con.execute('''INSERT INTO revision_events(event_id,proposal_id,occurred_at,event_type,from_state,to_state,
      proposal_hash,action_origin,note,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)''',
      (new_id('REV-EVT'), proposal['proposal_id'], now(), event_type, from_state, to_state,
       proposal['proposal_hash'], action_origin, note, json.dumps(metadata or {}, ensure_ascii=False)))
    con.commit()
    return dict(con.execute('SELECT * FROM revision_events WHERE seq=?', (cur.lastrowid,)).fetchone())


def propose_revision(con, *, account='default', project: str, chat: str, proposal_id: str,
                     artifact_id: str, base_version: str, original_request: str | None,
                     delta_summary: str, impact_summary: str, changed_sections: list[str],
                     base_sha256: str | None = None, source_ref: str | None = None,
                     parent_revision_id: str | None = None) -> dict:
    """Create an immutable, reviewable delta proposal. No full replacement artifact is generated or stored here."""
    for label, value in [('proposal_id', proposal_id), ('delta_summary', delta_summary),
                         ('impact_summary', impact_summary)]:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{label} must be non-empty')
    sections = [str(x).strip() for x in (changed_sections or []) if str(x).strip()]
    if not sections:
        raise ValueError('At least one changed section or affected component must be identified')
    if con.execute('SELECT 1 FROM revision_proposals WHERE proposal_id=?', (proposal_id,)).fetchone():
        raise ValueError(f'proposal_id already exists: {proposal_id}; proposals are immutable, use a new ID for a changed delta')

    if parent_revision_id:
        parent = _get_revision(con, parent_revision_id, account=account, project=project, chat=chat)
        parent_state = _revision_state(con, parent_revision_id)
        if parent_state != 'rejected_reset':
            raise ValueError('A clean re-plan can only start from a rejected/reset proposal')
        # Inherit the original task and stable artifact basis, never the rejected delta itself.
        original_request = parent['original_request']
        artifact_id = parent['artifact_id']
        base_version = base_version or parent['base_version']
        base_sha256 = base_sha256 if base_sha256 is not None else parent['base_sha256']
    if not isinstance(original_request, str) or not original_request.strip():
        raise ValueError('original_request must be non-empty for a new revision proposal')
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise ValueError('artifact_id must be non-empty')
    if not isinstance(base_version, str) or not base_version.strip():
        raise ValueError('base_version must be non-empty')

    payload = {
      'account_id': account, 'project_id': project, 'chat_id': chat, 'proposal_id': proposal_id,
      'artifact_id': artifact_id, 'base_version': base_version, 'base_sha256': base_sha256,
      'original_request': original_request, 'delta_summary': delta_summary, 'impact_summary': impact_summary,
      'changed_sections': sections, 'parent_revision_id': parent_revision_id, 'source_ref': source_ref
    }
    fingerprint = _revision_payload_hash(payload)
    con.execute('''INSERT INTO revision_proposals(proposal_id,account_id,project_id,chat_id,artifact_id,base_version,
      base_sha256,original_request,delta_summary,impact_summary,changed_sections_json,parent_revision_id,proposal_hash,source_ref,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (proposal_id, account, project, chat, artifact_id, base_version, base_sha256, original_request,
       delta_summary, impact_summary, json.dumps(sections, ensure_ascii=False), parent_revision_id,
       fingerprint, source_ref, now()))
    con.commit()
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    _append_revision_event(con, proposal=proposal, event_type='revision.proposed', from_state=None,
                           to_state='proposed', action_origin='assistant',
                           note='Structural delta proposed; full artifact has not been expanded.',
                           metadata={'parent_revision_id': parent_revision_id, 'source_ref': source_ref})
    return revision_preview(con, proposal_id, account=account, project=project, chat=chat)


def revision_preview(con, proposal_id: str, *, account: str | None = None,
                     project: str | None = None, chat: str | None = None) -> dict:
    """Return the approval-sized structural delta, never a replacement artifact."""
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    state = _revision_state(con, proposal_id)
    return {
      'proposal_id': proposal['proposal_id'], 'proposal_hash': proposal['proposal_hash'], 'state': state,
      'artifact_id': proposal['artifact_id'], 'base_version': proposal['base_version'],
      'base_sha256': proposal['base_sha256'], 'original_request': proposal['original_request'],
      'delta_summary': proposal['delta_summary'], 'impact_summary': proposal['impact_summary'],
      'changed_sections': proposal['changed_sections'], 'parent_revision_id': proposal['parent_revision_id'],
      'source_ref': proposal['source_ref'], 'created_at': proposal['created_at'],
      'approval_required_before_expansion': True,
      'next_action': 'explicit user decision: accept or reject'
    }


def revision_history(con, proposal_id: str, *, account: str | None = None,
                     project: str | None = None, chat: str | None = None) -> list[dict]:
    _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    return [dict(r) for r in con.execute('SELECT * FROM revision_events WHERE proposal_id=? ORDER BY seq',
                                         (proposal_id,)).fetchall()]


def decide_revision(con, proposal_id: str, decision: str, *, note: str = '',
                    account: str | None = None, project: str | None = None,
                    chat: str | None = None) -> dict:
    """Apply an explicit decision. Acceptance binds to the immutable proposal hash."""
    if decision not in {'accept', 'reject'}:
        raise ValueError("decision must be 'accept' or 'reject'")
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    state = _revision_state(con, proposal_id)
    if decision == 'accept':
        if state != 'proposed':
            raise ValueError(f'Cannot accept revision in state {state!r}; a fresh proposal is required')
        ev = _append_revision_event(con, proposal=proposal, event_type='revision.accepted', from_state=state,
                                    to_state='accepted_for_expansion', action_origin='user', note=note,
                                    metadata={'approved_proposal_hash': proposal['proposal_hash']})
        append_event(con, account=proposal['account_id'], project=proposal['project_id'], chat=proposal['chat_id'],
                     event_type='revision.accepted', provenance='user', authority='user_direct',
                     inference_kind='decision', truth_status='not_applicable',
                     source_ref=f"revision:{proposal_id}:{proposal['proposal_hash']}",
                     content=f"User accepted structural delta {proposal_id} for expansion.",
                     metadata={'proposal_hash': proposal['proposal_hash'], 'artifact_id': proposal['artifact_id'],
                               'base_version': proposal['base_version'], 'decision_note': note})
        return {'proposal_id': proposal_id, 'state': 'accepted_for_expansion',
                'approved_proposal_hash': proposal['proposal_hash'], 'event_seq': ev['seq'],
                'next_action': 'expand only this approved proposal'}

    if state not in {'proposed', 'accepted_for_expansion'}:
        raise ValueError(f'Cannot reject revision in state {state!r}')
    if con.execute('SELECT 1 FROM revision_outputs WHERE proposal_id=?', (proposal_id,)).fetchone():
        raise ValueError('An expanded artifact already exists; create a new proposal to revise it')
    _append_revision_event(con, proposal=proposal, event_type='revision.rejected', from_state=state,
                           to_state='rejected', action_origin='user', note=note,
                           metadata={'rejected_proposal_hash': proposal['proposal_hash']})
    # Preserve only the user's correction signal in the active event ledger; the rejected delta lives in the
    # separate immutable revision store and is not loaded into active model context.
    append_event(con, account=proposal['account_id'], project=proposal['project_id'], chat=proposal['chat_id'],
                 event_type='revision.rejected', provenance='user', authority='user_direct',
                 inference_kind='decision', truth_status='not_applicable',
                 source_ref=f"revision:{proposal_id}:{proposal['proposal_hash']}",
                 content=note or 'User rejected the proposed structural delta.',
                 metadata={'proposal_id': proposal_id, 'proposal_hash': proposal['proposal_hash'],
                           'artifact_id': proposal['artifact_id'], 'base_version': proposal['base_version']})
    reset = _append_revision_event(con, proposal=proposal, event_type='revision.reset', from_state='rejected',
                                   to_state='rejected_reset', action_origin='system',
                                   note='Rejected delta receives zero influence in the next plan; rehydrate from original request and stable artifact state.',
                                   metadata={'rejected_delta_excluded': True})
    return {'proposal_id': proposal_id, 'state': 'rejected_reset', 'retained_in_history': True,
            'rejected_delta_in_active_context': False, 'rejection_reason_retained': bool(note),
            'reset_event_seq': reset['seq'], 'next_action': 're-plan from original request and stable context'}


def revision_replan_context(con, proposal_id: str, *, account: str | None = None,
                            project: str | None = None, chat: str | None = None,
                            recent_assistant_turns: int = 6) -> dict:
    """Return clean re-plan basis. Deliberately omits the rejected delta text and impact summary."""
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    if _revision_state(con, proposal_id) != 'rejected_reset':
        raise ValueError('Re-plan context is available only after a rejected delta has been reset')
    history = revision_history(con, proposal_id, account=account, project=project, chat=chat)
    rejection = next((ev for ev in reversed(history) if ev['event_type'] in {'revision.rejected', 'revision.conformance_failed'}), None)
    payload = hydrate_payload(con, account=proposal['account_id'], project=proposal['project_id'],
                              chat=proposal['chat_id'], recent_assistant_turns=recent_assistant_turns)
    return {
      'rejected_proposal_id': proposal_id,
      'rejected_proposal_hash': proposal['proposal_hash'],
      'original_request': proposal['original_request'],
      'artifact_id': proposal['artifact_id'], 'base_version': proposal['base_version'],
      'base_sha256': proposal['base_sha256'],
      'user_correction_signal': rejection['note'] if rejection else '',
      'correction_signal_origin': rejection['action_origin'] if rejection else None,
      'stable_context': payload,
      'source_ref': proposal['source_ref'],
      'excluded_from_replan': ['rejected delta summary', 'rejected impact summary', 'rejected changed-section proposal'],
      'instruction': 'Develop a genuinely new delta from the original request, the unchanged artifact base, stable context, and the user correction signal. The rejected delta itself is historical only.'
    }


def expand_revision(con, proposal_id: str, *, artifact_version: str, content: str,
                    account: str | None = None, project: str | None = None,
                    chat: str | None = None, current_base_sha256: str | None = None) -> dict:
    """Persist the full artifact only after explicit approval of this exact proposal version.

    If the proposal recorded a base-artifact SHA-256, expansion fails closed unless the
    caller supplies the current base SHA-256 and it still matches. This prevents an
    approved delta from being applied against an artifact that changed after review.
    """
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    state = _revision_state(con, proposal_id)
    if state != 'accepted_for_expansion':
        raise ValueError(f'Full artifact expansion requires an accepted delta; current state is {state!r}')
    if not isinstance(artifact_version, str) or not artifact_version.strip():
        raise ValueError('artifact_version must be non-empty')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Expanded artifact content must be non-empty')
    if proposal['base_sha256'] is not None:
        if not isinstance(current_base_sha256, str) or not current_base_sha256.strip():
            raise ValueError('This proposal pinned a base SHA-256; current_base_sha256 is required before expansion')
        if current_base_sha256 != proposal['base_sha256']:
            raise ValueError('Base artifact changed after delta review; re-create the delta against the current base')
    accepted = [ev for ev in revision_history(con, proposal_id) if ev['event_type'] == 'revision.accepted']
    if not accepted or accepted[-1]['proposal_hash'] != proposal['proposal_hash'] or json.loads(accepted[-1]['metadata_json']).get('approved_proposal_hash') != proposal['proposal_hash']:
        raise ValueError('Approval does not match the immutable delta being expanded')
    out_id = new_id('ARTIFACT')
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    con.execute('''INSERT INTO revision_outputs(output_id,proposal_id,proposal_hash,artifact_version,content,content_sha256,created_at)
      VALUES(?,?,?,?,?,?,?)''', (out_id, proposal_id, proposal['proposal_hash'], artifact_version, content, content_hash, now()))
    con.commit()
    _append_revision_event(con, proposal=proposal, event_type='revision.expanded', from_state=state,
                           to_state='expanded', action_origin='assistant',
                           note='Expanded artifact stored after approval of this exact delta.',
                           metadata={'output_id': out_id, 'artifact_version': artifact_version, 'content_sha256': content_hash,
                                     'base_sha256': proposal['base_sha256'],
                                     'base_hash_checked': proposal['base_sha256'] is not None})
    append_event(con, account=proposal['account_id'], project=proposal['project_id'], chat=proposal['chat_id'],
                 event_type='revision.expanded', provenance='assistant', authority='delegated_execution',
                 inference_kind='generated_artifact', truth_status='not_applicable',
                 source_ref=f'revision-output:{out_id}',
                 content=f"Artifact {proposal['artifact_id']} expanded as {artifact_version} after accepted delta {proposal_id}; sha256={content_hash}.",
                 metadata={'proposal_id': proposal_id, 'proposal_hash': proposal['proposal_hash'],
                           'output_id': out_id, 'artifact_version': artifact_version, 'content_sha256': content_hash})
    return {'proposal_id': proposal_id, 'state': 'expanded', 'output_id': out_id,
            'artifact_version': artifact_version, 'content_sha256': content_hash,
            'approval_hash_matched': True, 'base_hash_checked': proposal['base_sha256'] is not None,
            'full_artifact_persisted': True}



def _markdown_section_blocks(text: str) -> dict[str, str]:
    '''Split Markdown into independently checkable heading blocks and preamble.

    Keys are `preamble` or `heading:<ancestor / ... / title>`. Each block spans
    its heading line up to (but not including) the next heading of any level.
    Duplicate normalized paths fail closed rather than becoming ambiguous.
    '''
    import re
    lines = text.splitlines(keepends=True)
    matches = []
    pat = re.compile(r'^(#{1,6})[ \t]+(.+?)\s*#*\s*(?:\r?\n)?$')
    stack: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = pat.match(line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        # The key's hierarchy is based on the structural Markdown outline.
        current_path = [x[1] for x in stack] + [title]
        key = 'heading:' + ' / '.join(current_path)
        matches.append((i, key))
        stack.append((level, title))
    if not matches:
        return {'preamble': text}
    blocks: dict[str, str] = {}
    if matches[0][0] > 0:
        preamble = ''.join(lines[:matches[0][0]])
        if preamble.strip():
            blocks['preamble'] = preamble
    for idx, (start, key) in enumerate(matches):
        end = matches[idx + 1][0] if idx + 1 < len(matches) else len(lines)
        if key in blocks:
            raise ValueError(f'Ambiguous Markdown section path {key!r}; use unique headings before verification')
        blocks[key] = ''.join(lines[start:end])
    return blocks


def _resolve_declared_sections(declared: list[str], base_blocks: dict[str, str],
                               candidate_blocks: dict[str, str]) -> tuple[set[str], list[str]]:
    '''Resolve user-facing changed-section selectors to exact block keys.'''
    all_keys = set(base_blocks) | set(candidate_blocks)
    resolved: set[str] = set()
    problems: list[str] = []
    if any(str(x).strip().casefold() in {'whole-artifact', '*'} for x in declared):
        return all_keys, problems
    for raw in declared:
        value = str(raw).strip()
        if not value:
            continue
        if value.casefold() == 'preamble':
            key = 'preamble'
            if key not in all_keys:
                problems.append(f"declared section 'preamble' not found")
            else:
                resolved.add(key)
            continue
        if value.casefold().startswith('heading:'):
            selector = value
            # Normalize whitespace but preserve case in display keys; match case-insensitively.
            suffix = ' / '.join(part.strip() for part in value[len('heading:'):].split('/'))
            matches = [k for k in all_keys if k.casefold() == ('heading:' + suffix).casefold()]
            if len(matches) == 1:
                resolved.add(matches[0])
            elif not matches:
                problems.append(f"declared section {selector!r} not found in base or proposed artifact")
            else:
                problems.append(f"declared section {selector!r} is ambiguous")
            continue
        # A bare heading is accepted only if it uniquely identifies a full path.
        norm = value.casefold()
        matches = [k for k in all_keys if k.startswith('heading:') and k[len('heading:'):].split(' / ')[-1].casefold() == norm]
        if len(matches) == 1:
            resolved.add(matches[0])
        elif not matches:
            problems.append(f"section {value!r} is not a verifiable Markdown heading; use heading:<exact path> or whole-artifact")
        else:
            problems.append(f"section {value!r} matches multiple headings; use the full heading path")
    return resolved, problems


def check_artifact_conformance(base_content: str, candidate_content: str,
                               declared_changed_sections: list[str]) -> dict:
    '''Check whether actual textual changes stay inside the accepted section scope.

    The check verifies scope, not semantic quality. To be machine-checkable, section
    declarations should use `heading:Exact / Heading Path`, `preamble`, or the explicit
    `whole-artifact` allowance. Vague prose such as "methodology paragraph" fails closed.
    '''
    base_hash = hashlib.sha256(base_content.encode('utf-8')).hexdigest()
    candidate_hash = hashlib.sha256(candidate_content.encode('utf-8')).hexdigest()
    report = {
        'schema_version': 1,
        'base_sha256': base_hash,
        'candidate_sha256': candidate_hash,
        'declared_changed_sections': [str(x).strip() for x in declared_changed_sections],
        'actual_changed_sections': [],
        'undeclared_changes': [],
        'declared_but_unchanged': [],
        'selector_problems': [],
        'added_line_count': 0,
        'removed_line_count': 0,
        'status': 'fail',
        'passed': False,
        'limits': ['Verifies textual scope, not whether the new text satisfies the approved semantic intent.'],
    }
    if base_content == candidate_content:
        report['status'] = 'fail'
        report['selector_problems'] = ['Candidate artifact is identical to the base; no approved change was applied.']
        return report
    try:
        base_blocks = _markdown_section_blocks(base_content)
        cand_blocks = _markdown_section_blocks(candidate_content)
    except ValueError as exc:
        report['status'] = 'unverifiable'
        report['selector_problems'] = [str(exc)]
        return report
    all_keys = set(base_blocks) | set(cand_blocks)
    actual = {key for key in all_keys if base_blocks.get(key) != cand_blocks.get(key)}
    declared, selector_problems = _resolve_declared_sections(declared_changed_sections, base_blocks, cand_blocks)
    report['actual_changed_sections'] = sorted(actual)
    whole_artifact = any(str(x).strip().casefold() in {'whole-artifact', '*'} for x in declared_changed_sections)
    report['undeclared_changes'] = [] if whole_artifact else sorted(actual - declared)
    report['declared_but_unchanged'] = [] if whole_artifact else sorted(declared - actual)
    report['selector_problems'] = selector_problems
    preview = delta_preview(base_content, candidate_content)
    report['added_line_count'] = preview['added_lines']
    report['removed_line_count'] = preview['removed_lines']
    if selector_problems:
        report['status'] = 'unverifiable'
    elif report['undeclared_changes'] or report['declared_but_unchanged']:
        report['status'] = 'fail'
    else:
        report['status'] = 'pass'
        report['passed'] = True
    return report


def verify_revision_output(con, proposal_id: str, *, base_content: str,
                           account: str | None = None, project: str | None = None,
                           chat: str | None = None) -> dict:
    '''Verify latest expanded output against pinned base and approved changed-section scope.

    A failed conformance check transitions the proposal to rejected_reset so it can only
    be retried through a fresh delta. The output remains immutable history and is not
    reported as ready for release.
    '''
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    state = _revision_state(con, proposal_id)
    if state != 'expanded':
        raise ValueError(f'Conformance verification requires an expanded output; current state is {state!r}')
    output = con.execute('SELECT * FROM revision_outputs WHERE proposal_id=? ORDER BY created_at DESC LIMIT 1',
                         (proposal_id,)).fetchone()
    if not output:
        raise ValueError(f'No expanded artifact exists for revision {proposal_id!r}')
    output = dict(output)
    actual_output_hash = hashlib.sha256(output['content'].encode('utf-8')).hexdigest()
    if actual_output_hash != output['content_sha256']:
        raise RuntimeError('Stored output hash mismatch; immutable output integrity is compromised')

    computed_base_hash = hashlib.sha256(base_content.encode('utf-8')).hexdigest()
    declared = list(proposal['changed_sections'])
    if not proposal['base_sha256']:
        report = {
            'schema_version': 1, 'base_sha256': computed_base_hash,
            'candidate_sha256': output['content_sha256'], 'declared_changed_sections': declared,
            'actual_changed_sections': [], 'undeclared_changes': [], 'declared_but_unchanged': [],
            'selector_problems': ['Proposal did not pin a base SHA-256 when the delta was reviewed. Recreate proposal against a pinned base.'],
            'added_line_count': 0, 'removed_line_count': 0, 'status': 'unverifiable', 'passed': False,
            'limits': ['No independent proof that the supplied base is the same artifact used at proposal time.'],
        }
    elif computed_base_hash != proposal['base_sha256']:
        report = {
            'schema_version': 1, 'base_sha256': computed_base_hash,
            'candidate_sha256': output['content_sha256'], 'declared_changed_sections': declared,
            'actual_changed_sections': [], 'undeclared_changes': [], 'declared_but_unchanged': [],
            'selector_problems': ['Current base content does not match the SHA-256 pinned in the accepted proposal.'],
            'added_line_count': 0, 'removed_line_count': 0, 'status': 'fail', 'passed': False,
            'limits': ['Output was not compared against a stale or mismatched base.'],
        }
    else:
        report = check_artifact_conformance(base_content, output['content'], declared)
        report['base_hash_matched_proposal'] = True
        report['proposal_hash'] = proposal['proposal_hash']
        report['proposal_id'] = proposal_id
        report['output_id'] = output['output_id']

    status = report['status'] if report['status'] in {'pass','fail','unverifiable'} else 'fail'
    check_id = new_id('CONF')
    con.execute('''INSERT INTO revision_conformance_checks(check_id,proposal_id,proposal_hash,base_sha256,output_sha256,status,report_json,created_at)
      VALUES(?,?,?,?,?,?,?,?)''', (check_id, proposal_id, proposal['proposal_hash'], computed_base_hash,
       output['content_sha256'], status, json.dumps(report, ensure_ascii=False, sort_keys=True), now()))
    con.commit()
    if report['passed']:
        _append_revision_event(con, proposal=proposal, event_type='revision.conformance_passed', from_state='expanded',
                               to_state='expanded', action_origin='system',
                               note='Output stays within the approved changed-section scope.',
                               metadata={'check_id': check_id, 'output_sha256': output['content_sha256']})
    else:
        correction = '; '.join(report.get('selector_problems', []) +
                               ([f"Changes outside approved scope: {', '.join(report['undeclared_changes'])}"] if report.get('undeclared_changes') else []) +
                               ([f"Declared sections not changed: {', '.join(report['declared_but_unchanged'])}"] if report.get('declared_but_unchanged') else []))
        _append_revision_event(con, proposal=proposal, event_type='revision.conformance_failed', from_state='expanded',
                               to_state='rejected_reset', action_origin='system',
                               note=correction or 'Artifact did not conform to its accepted delta; reset and re-plan.',
                               metadata={'check_id': check_id, 'output_sha256': output['content_sha256'], 'failed_closed': True})
        append_event(con, account=proposal['account_id'], project=proposal['project_id'], chat=proposal['chat_id'],
                     event_type='revision.conformance_failed', provenance='system', authority='system_process',
                     inference_kind='process_event', truth_status='not_applicable',
                     source_ref=f'revision-conformance:{check_id}',
                     content=correction or 'Expanded artifact did not conform to its accepted delta; a fresh proposal is required.',
                     metadata={'proposal_id': proposal_id, 'proposal_hash': proposal['proposal_hash'], 'check_id': check_id})
    report.update({'check_id': check_id, 'proposal_id': proposal_id, 'proposal_hash': proposal['proposal_hash'],
                   'output_id': output['output_id'], 'status': status, 'passed': bool(report.get('passed')),
                   'ready_for_release': bool(report.get('passed'))})
    return report


def revision_conformance_history(con, proposal_id: str) -> list[dict]:
    rows = con.execute('SELECT * FROM revision_conformance_checks WHERE proposal_id=? ORDER BY rowid',
                       (proposal_id,)).fetchall()
    return [{**dict(r), 'report': json.loads(r['report_json'])} for r in rows]

def revision_output(con, proposal_id: str) -> dict:
    row = con.execute('SELECT * FROM revision_outputs WHERE proposal_id=? ORDER BY created_at DESC LIMIT 1',
                       (proposal_id,)).fetchone()
    if not row:
        raise ValueError(f'No expanded artifact exists for proposal {proposal_id!r}')
    result = dict(row)
    checks = revision_conformance_history(con, proposal_id)
    latest = checks[-1] if checks else None
    result['conformance_status'] = latest['status'] if latest else 'unverified'
    result['ready_for_release'] = bool(latest and latest['status'] == 'pass' and latest['report'].get('passed'))
    result['latest_conformance_check_id'] = latest['check_id'] if latest else None
    return result


def ensure_distinct_output_paths(primary: str | Path, audit: str | Path) -> tuple[Path, Path]:
    """Resolve and validate separate artifact and runtime-audit destinations."""
    primary_path = Path(primary).expanduser().resolve()
    audit_path = Path(audit).expanduser().resolve()
    if primary_path == audit_path:
        raise ValueError('Response/model-input output and audit sidecar must use different file paths')
    return primary_path, audit_path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default=str(default_data_dir() / 'ael.sqlite3'))
    p.add_argument('--account', default='default')
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record'); r.add_argument('--project', required=True); r.add_argument('--chat', required=True); r.add_argument('--type', dest='event_type', required=True); r.add_argument('--provenance', choices=sorted(VALID_PROVENANCE), required=True); r.add_argument('--content', required=True); r.add_argument('--authority', choices=sorted(VALID_AUTHORITIES), default='none'); r.add_argument('--inference-kind', choices=sorted(VALID_INFERENCE_KINDS), default='unspecified'); r.add_argument('--truth-status', choices=sorted(VALID_TRUTH_STATUSES), default='unverified'); r.add_argument('--source-ref'); r.add_argument('--branch'); r.add_argument('--strategy-key'); r.add_argument('--metadata', default='{}')
    g = sub.add_parser('gate'); g.add_argument('--project', required=True); g.add_argument('--chat', required=True); g.add_argument('--decision', choices=['single','clarify','branch','recommend','just_pick','branch_it'], required=True); g.add_argument('--original-query')
    b = sub.add_parser('branch'); b.add_argument('--project', required=True); b.add_argument('--chat', required=True); b.add_argument('--id', required=True); b.add_argument('--label', required=True); b.add_argument('--tradeoff', required=True); b.add_argument('--strategy-key', required=True); b.add_argument('--original-query')
    d = sub.add_parser('decide'); d.add_argument('--project', required=True); d.add_argument('--chat', required=True); d.add_argument('--id', required=True); d.add_argument('--status', choices=['selected','rejected','completed'], required=True); d.add_argument('--note', default=''); d.add_argument('--decision-path', choices=['direct','accepted_recommendation','system'], default='direct'); d.add_argument('--strategy-failure', action='store_true'); d.add_argument('--threshold', type=int, default=3); d.add_argument('--usage-status', choices=sorted(BRANCH_REUSE_STATUSES), default='not_pertinent_now')
    h = sub.add_parser('hydrate'); h.add_argument('--project', required=True); h.add_argument('--chat', required=True); h.add_argument('--relevance-tags', nargs='*', help='Explicit tags relevant to this task')
    mc = sub.add_parser('model-context'); mc.add_argument('--project', required=True); mc.add_argument('--chat', required=True); mc.add_argument('--max-tokens', type=int, default=12000); mc.add_argument('--recent-assistant-turns', type=int, default=6); mc.add_argument('--relevance-tags', nargs='*', help='Tags/strategy keys applicable to this task')
    mi = sub.add_parser('model-input'); mi.add_argument('--project', required=True); mi.add_argument('--chat', required=True); mi.add_argument('--current-user-message', required=True); mi.add_argument('--max-tokens', type=int, default=12000); mi.add_argument('--recent-assistant-turns', type=int, default=6); mi.add_argument('--relevance-tags', nargs='*', help='Explicitly applicable memory tags'); mi.add_argument('--out', required=True); mi.add_argument('--audit-out', required=True)
    oc = sub.add_parser('ollama-chat', help='Send the allowlisted active context to a loopback-only local Ollama model; no API key'); oc.add_argument('--project', required=True); oc.add_argument('--chat', required=True); oc.add_argument('--current-user-message', required=True); oc.add_argument('--model', required=True); oc.add_argument('--endpoint', default='http://127.0.0.1:11434'); oc.add_argument('--timeout', type=float, default=120.0); oc.add_argument('--max-tokens', type=int, default=12000); oc.add_argument('--recent-assistant-turns', type=int, default=6); oc.add_argument('--relevance-tags', nargs='*', help='Explicitly applicable memory tags'); oc.add_argument('--out', required=True); oc.add_argument('--audit-out', required=True)
    os = sub.add_parser('ollama-status', help='Check a loopback Ollama service and list locally available models; no prompt is sent'); os.add_argument('--endpoint', default='http://127.0.0.1:11434'); os.add_argument('--timeout', type=float, default=3.0)
    c = sub.add_parser('checkpoint'); c.add_argument('--project', required=True); c.add_argument('--chat', required=True); c.add_argument('--out', default='handoffs')
    m = sub.add_parser('memory'); ms = m.add_subparsers(dest='memory_cmd', required=True)
    mp = ms.add_parser('propose'); mp.add_argument('--scope', choices=['account','project'], required=True); mp.add_argument('--project'); mp.add_argument('--tag', required=True); mp.add_argument('--claim', required=True); mp.add_argument('--source-event-seq', type=int); mp.add_argument('--weight', type=float, default=1.0)
    mr = ms.add_parser('review'); mr.add_argument('--id', required=True); mr.add_argument('--decision', choices=['accept','edit','reject'], required=True); mr.add_argument('--claim'); mr.add_argument('--note', default='')
    mre = ms.add_parser('reopen'); mre.add_argument('--id', required=True); mre.add_argument('--note', default='')
    mres = ms.add_parser('resolve'); mres.add_argument('--id', required=True); mres.add_argument('--decision', choices=['use','avoid','later','not_pertinent_now','keep'], required=True); mres.add_argument('--note', default='')
    mrb = ms.add_parser('batch-resolve'); mrb.add_argument('--ids', nargs='+', required=True); mrb.add_argument('--decision', choices=['use','avoid','later','not_pertinent_now','keep'], required=True); mrb.add_argument('--note', default='')
    mu = ms.add_parser('set-usage'); mu.add_argument('--id', required=True); mu.add_argument('--status', choices=sorted(VALID_USAGE_STATUSES), required=True); mu.add_argument('--note', default='')
    ma = ms.add_parser('set-state'); ma.add_argument('--id', required=True); ma.add_argument('--action', choices=['ratify','dormant','reverse','reactivate','confirm'], required=True); ma.add_argument('--note', default='')
    ml = ms.add_parser('list'); ml.add_argument('--project'); ml.add_argument('--tag'); ml.add_argument('--include-local', action='store_true'); ml.add_argument('--include-discarded', action='store_true')
    rv = sub.add_parser('revision'); rvs = rv.add_subparsers(dest='revision_cmd', required=True)
    rvp = rvs.add_parser('propose'); rvp.add_argument('--project', required=True); rvp.add_argument('--chat', required=True); rvp.add_argument('--id', required=True); rvp.add_argument('--artifact-id', required=True); rvp.add_argument('--base-version', required=True); rvp.add_argument('--original-request', required=True); rvp.add_argument('--delta-summary', required=True); rvp.add_argument('--impact-summary', required=True); rvp.add_argument('--changed-section', nargs='+', required=True); rvp.add_argument('--base-sha256'); rvp.add_argument('--source-ref')
    rvsw = rvs.add_parser('show'); rvsw.add_argument('--id', required=True)
    rvh = rvs.add_parser('history'); rvh.add_argument('--id', required=True)
    rvd = rvs.add_parser('decide'); rvd.add_argument('--id', required=True); rvd.add_argument('--decision', choices=['accept','reject'], required=True); rvd.add_argument('--note', default='')
    rvr = rvs.add_parser('replan'); rvr.add_argument('--project', required=True); rvr.add_argument('--chat', required=True); rvr.add_argument('--from-id', required=True); rvr.add_argument('--id', required=True); rvr.add_argument('--delta-summary', required=True); rvr.add_argument('--impact-summary', required=True); rvr.add_argument('--changed-section', nargs='+', required=True); rvr.add_argument('--base-version'); rvr.add_argument('--base-sha256'); rvr.add_argument('--source-ref')
    rvc = rvs.add_parser('replan-context'); rvc.add_argument('--id', required=True); rvc.add_argument('--project', required=True); rvc.add_argument('--chat', required=True)
    rve = rvs.add_parser('expand'); rve.add_argument('--id', required=True); rve.add_argument('--artifact-version', required=True); rve.add_argument('--content-file', required=True); rve.add_argument('--current-base-sha256', help='Required at expansion if the proposal pinned --base-sha256')
    rvo = rvs.add_parser('get-output'); rvo.add_argument('--id', required=True); rvo.add_argument('--out', required=True); rvo.add_argument('--allow-unverified', action='store_true', help='Explicitly export an output that has not passed conformance; not recommended')
    rvv = rvs.add_parser('verify-output'); rvv.add_argument('--id', required=True); rvv.add_argument('--base-file', required=True); rvv.add_argument('--report-out')
    rvvh = rvs.add_parser('verification-history'); rvvh.add_argument('--id', required=True)
    import ael_task_precommitment as task_precommitment
    task_precommitment.add_cli_parser(sub)
    a = p.parse_args()
    if a.cmd == 'ollama-status':
      status = ollama_status(a.endpoint, timeout=a.timeout)
      print(json.dumps(status, ensure_ascii=False, indent=2))
      return 0 if status.get('available') else 2
    con = connect(a.db)
    try:
      if a.cmd == 'task':
        return task_precommitment.dispatch(con, sys.modules[__name__], a, account=a.account)
      if a.cmd == 'record':
        e=append_event(con, account=a.account, project=a.project, chat=a.chat, event_type=a.event_type, provenance=a.provenance, content=a.content,
          authority=a.authority, inference_kind=a.inference_kind, truth_status=a.truth_status, source_ref=a.source_ref,
          branch_id=a.branch, strategy_key=a.strategy_key, metadata=json.loads(a.metadata))
        print(json.dumps({'recorded': True, 'seq': e['seq'], 'event_id': e['event_id']}, indent=2))
      elif a.cmd == 'gate':
        if a.original_query and not con.execute(
          "SELECT 1 FROM events WHERE account_id=? AND project_id=? AND chat_id=? AND event_type='original_query' LIMIT 1",
          (a.account,a.project,a.chat)).fetchone():
          append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='original_query',provenance='user',
            authority='user_direct',inference_kind='user_statement',truth_status='not_applicable',content=a.original_query)
        result=gate_message(a.decision)
        append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='materiality_gate.override' if a.decision in {'just_pick','branch_it'} else 'materiality_gate.assessed',
          provenance='user' if a.decision in {'just_pick','branch_it'} else 'system',authority='user_direct' if a.decision in {'just_pick','branch_it'} else 'system_process',
          inference_kind='process_event',truth_status='not_applicable',content=result['message'],metadata={'decision':a.decision,'original_query':a.original_query})
        print(json.dumps(result, indent=2))
      elif a.cmd == 'branch':
        propose_branch(con, account=a.account, project=a.project, chat=a.chat, branch_id=a.id, label=a.label,
          tradeoff=a.tradeoff, strategy_key=a.strategy_key, original_query=a.original_query)
        print(f'Proposed branch {a.id}: {a.label}; trade-off: {a.tradeoff}')
      elif a.cmd == 'decide':
        result=decide_branch(con, account=a.account, project=a.project, chat=a.chat, branch_id=a.id, status=a.status,
          note=a.note, decision_path=a.decision_path, strategy_failure=a.strategy_failure, threshold=a.threshold, usage_status=a.usage_status)
        print(json.dumps({'branch_id':a.id,'status':a.status,'circuit_breaker':result}, indent=2))
      elif a.cmd == 'hydrate':
        print(render_markdown(hydrate_payload(con, account=a.account, project=a.project, chat=a.chat, relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)))
      elif a.cmd == 'model-context':
        payload=hydrate_payload(con,account=a.account,project=a.project,chat=a.chat,recent_assistant_turns=a.recent_assistant_turns,relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)
        packed=render_model_context(payload,max_tokens=a.max_tokens)
        print(json.dumps(packed,ensure_ascii=False,indent=2))
      elif a.cmd == 'model-input':
        ensure_distinct_output_paths(a.out, a.audit_out)
        payload=hydrate_payload(con,account=a.account,project=a.project,chat=a.chat,recent_assistant_turns=a.recent_assistant_turns,relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)
        model_input, audit = build_model_input(payload,a.current_user_message,max_tokens=a.max_tokens)
        out, audit_out = ensure_distinct_output_paths(a.out, a.audit_out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(model_input,ensure_ascii=False,indent=2),encoding='utf-8')
        audit_out.parent.mkdir(parents=True,exist_ok=True); audit_out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'model_input_path':str(out),'audit_path':str(audit_out),'model_input_keys':sorted(model_input.keys()),'audit_separate':out.resolve()!=audit_out.resolve()},indent=2))
      elif a.cmd == 'ollama-chat':
        ensure_distinct_output_paths(a.out, a.audit_out)
        # Hydrate and pack before adding the current query to history; this prevents duplicating it in the context.
        payload=hydrate_payload(con,account=a.account,project=a.project,chat=a.chat,recent_assistant_turns=a.recent_assistant_turns,relevance_tags=set(a.relevance_tags) if a.relevance_tags is not None else None)
        # Reserve a rough estimate for the adapter's fixed system prompt, delimiters and current user message.
        reserve_text=OLLAMA_SYSTEM_PROMPT + a.current_user_message + '=== BOUNDED WORKING CONTEXT === === CURRENT USER MESSAGE ==='
        reserved=rough_token_estimate(reserve_text)
        model_input, audit = build_model_input(payload,a.current_user_message,max_tokens=a.max_tokens,reserved_tokens=reserved)
        user_event=append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='user_request',provenance='user',authority='user_direct',inference_kind='user_statement',truth_status='not_applicable',content=a.current_user_message,metadata={'context_sha256':audit['context_sha256'],'model':a.model,'transport':'ollama-local'})
        try:
          response=ollama_chat(model_input,model=a.model,base_url=a.endpoint,timeout=a.timeout)
        except Exception as exc:
          audit.update({'provider':'ollama-local','model':a.model,'call_status':'failed','failure_type':type(exc).__name__,
                        'api_token_used':False,'user_event_seq':user_event['seq']})
          out_path, audit_out = ensure_distinct_output_paths(a.out, a.audit_out); audit_out.parent.mkdir(parents=True,exist_ok=True); audit_out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
          raise
        assistant_event=append_event(con,account=a.account,project=a.project,chat=a.chat,event_type='assistant_turn',provenance='assistant',authority='none',inference_kind='inference',truth_status='unverified',source_ref=f"ollama:{response['model']}",content=response['content'],metadata={'context_sha256':audit['context_sha256'],'in_reply_to_seq':user_event['seq'],'model':response['model'],'metrics':response['metrics']})
        audit.update({'provider':'ollama-local','model':response['model'],'endpoint_host':response['endpoint_host'],'api_token_used':False,'call_status':'success','user_event_seq':user_event['seq'],'assistant_event_seq':assistant_event['seq'],'token_counter_warning':'The active context budget uses the offline estimate unless a provider-specific counter is injected.'})
        out, audit_out = ensure_distinct_output_paths(a.out, a.audit_out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({'provider':response['provider'],'model':response['model'],'content':response['content'],'done':response['done'],'metrics':response['metrics'],'user_event_seq':user_event['seq'],'assistant_event_seq':assistant_event['seq']},ensure_ascii=False,indent=2),encoding='utf-8')
        audit_out.parent.mkdir(parents=True,exist_ok=True); audit_out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'response_path':str(out),'audit_path':str(audit_out),'provider':'ollama-local','model':response['model'],'api_token_used':False,'audit_separate':out.resolve()!=audit_out.resolve()},indent=2))
      elif a.cmd == 'checkpoint':
        md,js=checkpoint(con,account=a.account,project=a.project,chat=a.chat,out_dir=a.out)
        print(json.dumps({'markdown':str(md),'json':str(js),'verified':md.is_file() and json.loads(js.read_text(encoding='utf-8'))['schema_version']==2},indent=2))
      elif a.cmd == 'memory':
        if a.memory_cmd == 'propose':
          mid=add_memory(con,account=a.account,scope=a.scope,tag=a.tag,claim=a.claim,project=a.project,source_event_seq=a.source_event_seq,weight=a.weight)
          print(json.dumps({'memory_id':mid,'state':'pending','stage':'local_candidate','next_step':f'memory review --id {mid} --decision accept|edit|reject','influence_permission':False},indent=2))
        elif a.memory_cmd == 'review':
          result=review_memory_claim(con,a.id,a.decision,edited_claim=a.claim,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'reopen':
          result=reopen_memory_candidate(con,a.id,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'resolve':
          result=resolve_memory_reference(con,a.id,a.decision,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'batch-resolve':
          result=resolve_memory_batch(con,a.ids,a.decision,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        elif a.memory_cmd == 'set-state':
          change_memory_state(con,a.id,a.action,note=a.note); print(json.dumps({'memory_id':a.id,'action':a.action,'updated':True},indent=2))
        elif a.memory_cmd == 'set-usage':
          result=set_memory_usage_status(con,a.id,a.status,note=a.note); print(json.dumps(result,ensure_ascii=False,indent=2))
        else:
          print(json.dumps(list_memories(con,account=a.account,project=a.project,tag=a.tag,include_local=a.include_local,include_discarded=a.include_discarded),ensure_ascii=False,indent=2))
      elif a.cmd == 'revision':
        if a.revision_cmd == 'propose':
          result = propose_revision(con, account=a.account, project=a.project, chat=a.chat, proposal_id=a.id,
            artifact_id=a.artifact_id, base_version=a.base_version, original_request=a.original_request,
            delta_summary=a.delta_summary, impact_summary=a.impact_summary, changed_sections=a.changed_section,
            base_sha256=a.base_sha256, source_ref=a.source_ref)
          print(json.dumps(result, ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'show':
          print(json.dumps(revision_preview(con, a.id, account=a.account), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'history':
          print(json.dumps(revision_history(con, a.id, account=a.account), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'decide':
          print(json.dumps(decide_revision(con, a.id, a.decision, note=a.note, account=a.account), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'replan':
          parent = _get_revision(con, a.from_id, account=a.account, project=a.project, chat=a.chat)
          result = propose_revision(con, account=a.account, project=a.project, chat=a.chat, proposal_id=a.id,
            artifact_id=parent['artifact_id'], base_version=a.base_version or parent['base_version'],
            original_request=parent['original_request'], delta_summary=a.delta_summary,
            impact_summary=a.impact_summary, changed_sections=a.changed_section,
            base_sha256=a.base_sha256, source_ref=a.source_ref, parent_revision_id=a.from_id)
          print(json.dumps(result, ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'replan-context':
          print(json.dumps(revision_replan_context(con, a.id, account=a.account, project=a.project, chat=a.chat), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'expand':
          content = Path(a.content_file).read_text(encoding='utf-8')
          print(json.dumps(expand_revision(con, a.id, artifact_version=a.artifact_version, content=content, account=a.account, current_base_sha256=a.current_base_sha256), ensure_ascii=False, indent=2))
        elif a.revision_cmd == 'verify-output':
          base = Path(a.base_file).read_text(encoding='utf-8')
          report = verify_revision_output(con,a.id,base_content=base,account=a.account)
          if a.report_out:
            report_path=Path(a.report_out); report_path.parent.mkdir(parents=True,exist_ok=True); report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
          print(json.dumps(report,ensure_ascii=False,indent=2))
        elif a.revision_cmd == 'verification-history':
          print(json.dumps(revision_conformance_history(con,a.id),ensure_ascii=False,indent=2))
        else:
          result = revision_output(con, a.id)
          if not result['ready_for_release'] and not a.allow_unverified:
            raise ValueError(f"Output is not ready for release (conformance_status={result['conformance_status']!r}). Run revision verify-output with the exact base file, or use --allow-unverified only for explicit inspection.")
          out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(result['content'], encoding='utf-8')
          print(json.dumps({'output_id': result['output_id'], 'out': str(out), 'artifact_version': result['artifact_version'], 'content_sha256': result['content_sha256'], 'conformance_status':result['conformance_status'],'ready_for_release':result['ready_for_release'],'verified': out.is_file()}, ensure_ascii=False, indent=2))
    finally:
      con.close()

if __name__ == '__main__':
    raise SystemExit(main())
