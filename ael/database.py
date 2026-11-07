"""Shared SQLite schema, connection setup and compatibility migrations."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from .config import SYSTEM_ACTOR_ID, ASSISTANT_ACTOR_ID, UNKNOWN_USER_ACTOR_ID, UNKNOWN_EXTERNAL_ACTOR_ID, UNKNOWN_ACTOR_ID

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
  metadata_json TEXT NOT NULL DEFAULT '{}',
  actor_id TEXT NOT NULL DEFAULT 'ael:actor:unattributed',
  on_behalf_of_id TEXT,
  recorded_by_id TEXT NOT NULL DEFAULT 'ael:system:runtime'
);
CREATE INDEX IF NOT EXISTS ix_events_scope ON events(account_id, project_id, chat_id, seq);
CREATE INDEX IF NOT EXISTS ix_events_branch ON events(branch_id, seq);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'event ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'event ledger is append-only'); END;
CREATE TABLE IF NOT EXISTS participants (
  account_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  participant_type TEXT NOT NULL CHECK(participant_type IN ('human','ai_agent','service','system','unknown')),
  identity_source TEXT NOT NULL CHECK(identity_source IN ('organisation','self_generated','provider','system','unattributed')),
  issuer TEXT,
  external_id TEXT,
  display_name TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(account_id, participant_id),
  UNIQUE(account_id, identity_source, issuer, external_id)
);
CREATE INDEX IF NOT EXISTS ix_participants_name ON participants(account_id, display_name);
CREATE TABLE IF NOT EXISTS participation_periods (
  participation_period_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  workflow_id TEXT,
  participant_id TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'participant',
  started_by_event_id TEXT NOT NULL,
  effective_from_seq INTEGER NOT NULL,
  ended_by_event_id TEXT,
  effective_until_seq INTEGER,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK(effective_from_seq > 0),
  CHECK(effective_until_seq IS NULL OR effective_until_seq > effective_from_seq),
  FOREIGN KEY(account_id, participant_id) REFERENCES participants(account_id, participant_id)
);
CREATE INDEX IF NOT EXISTS ix_participation_scope ON participation_periods(account_id, project_id, chat_id, effective_from_seq, effective_until_seq);
CREATE INDEX IF NOT EXISTS ix_participation_actor ON participation_periods(account_id, participant_id, effective_from_seq);
CREATE UNIQUE INDEX IF NOT EXISTS ux_participation_active ON participation_periods(account_id, project_id, chat_id, ifnull(workflow_id, ''), participant_id) WHERE effective_until_seq IS NULL;
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
  note TEXT NOT NULL DEFAULT '',
  actor_id TEXT NOT NULL DEFAULT 'ael:actor:unattributed',
  on_behalf_of_id TEXT,
  recorded_by_id TEXT NOT NULL DEFAULT 'ael:system:runtime'
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
  source_relative_path TEXT,
  source_byte_length INTEGER,
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
  actor_id TEXT NOT NULL DEFAULT 'ael:actor:unattributed',
  on_behalf_of_id TEXT,
  recorded_by_id TEXT NOT NULL DEFAULT 'ael:system:runtime',
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

def connect(db_path: str | Path) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    con.executescript(SCHEMA)
    # Actor attribution is additive. Older rows receive explicit unattributed
    # actor IDs rather than guessed identities.
    column_migrations = {
        'events': [
            ("actor_id", "TEXT NOT NULL DEFAULT 'ael:actor:unattributed'"),
            ("on_behalf_of_id", "TEXT"),
            ("recorded_by_id", "TEXT NOT NULL DEFAULT 'ael:system:runtime'"),
        ],
        'memory_events': [
            ("actor_id", "TEXT NOT NULL DEFAULT 'ael:actor:unattributed'"),
            ("on_behalf_of_id", "TEXT"),
            ("recorded_by_id", "TEXT NOT NULL DEFAULT 'ael:system:runtime'"),
        ],
        'revision_events': [
            ("actor_id", "TEXT NOT NULL DEFAULT 'ael:actor:unattributed'"),
            ("on_behalf_of_id", "TEXT"),
            ("recorded_by_id", "TEXT NOT NULL DEFAULT 'ael:system:runtime'"),
        ],
    }
    for table, columns in column_migrations.items():
        existing = {r['name'] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}
        for column, declaration in columns:
            if column not in existing:
                con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
    # Seed reserved actors and any actor IDs already present in a database that
    # was created by an intermediate build. Their identity remains explicitly
    # unknown until an authorised identity source resolves it.
    reserved = [
        ('ael:actor:unknown-user', 'unknown', 'unattributed', 'Unattributed user'),
        ('ael:actor:unknown-external', 'unknown', 'unattributed', 'Unattributed external actor'),
        ('ael:actor:unattributed', 'unknown', 'unattributed', 'Unattributed actor'),
        ('ael:agent:assistant', 'ai_agent', 'system', 'AEL assistant agent'),
        ('ael:system:runtime', 'system', 'system', 'AEL runtime'),
    ]
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    for participant_id, participant_type, identity_source, display_name in reserved:
        con.execute(
            """INSERT OR IGNORE INTO participants
               (account_id,participant_id,participant_type,identity_source,display_name,created_at,updated_at)
               VALUES('default',?,?,?,?,?,?)""",
            (participant_id, participant_type, identity_source, display_name, stamp, stamp)
        )
    for row in con.execute("SELECT DISTINCT account_id, actor_id FROM events WHERE actor_id IS NOT NULL").fetchall():
        con.execute(
            """INSERT OR IGNORE INTO participants
               (account_id,participant_id,participant_type,identity_source,display_name,created_at,updated_at)
               VALUES(?,?,'unknown','unattributed',?,?,?)""",
            (row['account_id'], row['actor_id'], row['actor_id'], stamp, stamp)
        )
    for row in con.execute("SELECT DISTINCT account_id, recorded_by_id FROM events WHERE recorded_by_id IS NOT NULL").fetchall():
        con.execute(
            """INSERT OR IGNORE INTO participants
               (account_id,participant_id,participant_type,identity_source,display_name,created_at,updated_at)
               VALUES(?,?,'system','system',?,?,?)""",
            (row['account_id'], row['recorded_by_id'], row['recorded_by_id'], stamp, stamp)
        )
    legacy_actor_queries = [
        """SELECT DISTINCT m.account_id, me.actor_id AS participant_id, 'unknown' AS participant_type,
                  'unattributed' AS identity_source
           FROM memory_events me JOIN memories m ON m.memory_id=me.memory_id
           WHERE me.actor_id IS NOT NULL
           UNION SELECT DISTINCT m.account_id, me.recorded_by_id, 'system', 'system'
           FROM memory_events me JOIN memories m ON m.memory_id=me.memory_id
           WHERE me.recorded_by_id IS NOT NULL
           UNION SELECT DISTINCT m.account_id, me.on_behalf_of_id, 'unknown', 'unattributed'
           FROM memory_events me JOIN memories m ON m.memory_id=me.memory_id
           WHERE me.on_behalf_of_id IS NOT NULL
           UNION SELECT DISTINCT c.account_id, me.actor_id, 'unknown', 'unattributed'
           FROM memory_events me JOIN memory_candidates c ON c.candidate_id=me.memory_id
           WHERE me.actor_id IS NOT NULL
           UNION SELECT DISTINCT c.account_id, me.recorded_by_id, 'system', 'system'
           FROM memory_events me JOIN memory_candidates c ON c.candidate_id=me.memory_id
           WHERE me.recorded_by_id IS NOT NULL
           UNION SELECT DISTINCT c.account_id, me.on_behalf_of_id, 'unknown', 'unattributed'
           FROM memory_events me JOIN memory_candidates c ON c.candidate_id=me.memory_id
           WHERE me.on_behalf_of_id IS NOT NULL
           UNION SELECT DISTINCT p.account_id, re.actor_id, 'unknown', 'unattributed'
           FROM revision_events re JOIN revision_proposals p ON p.proposal_id=re.proposal_id
           WHERE re.actor_id IS NOT NULL
           UNION SELECT DISTINCT p.account_id, re.recorded_by_id, 'system', 'system'
           FROM revision_events re JOIN revision_proposals p ON p.proposal_id=re.proposal_id
           WHERE re.recorded_by_id IS NOT NULL
           UNION SELECT DISTINCT p.account_id, re.on_behalf_of_id, 'unknown', 'unattributed'
           FROM revision_events re JOIN revision_proposals p ON p.proposal_id=re.proposal_id
           WHERE re.on_behalf_of_id IS NOT NULL""",
    ]
    for query in legacy_actor_queries:
        for row in con.execute(query).fetchall():
            con.execute(
                """INSERT OR IGNORE INTO participants
                   (account_id,participant_id,participant_type,identity_source,display_name,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (row['account_id'], row['participant_id'], row['participant_type'],
                 row['identity_source'], row['participant_id'], stamp, stamp)
            )
    # Preserve the correct built-in types even if those IDs were first seen
    # through a legacy row whose new attribution columns defaulted to unknown.
    builtins = [
        (SYSTEM_ACTOR_ID, 'system', 'system', 'AEL runtime'),
        (ASSISTANT_ACTOR_ID, 'ai_agent', 'system', 'AEL assistant agent'),
        (UNKNOWN_USER_ACTOR_ID, 'unknown', 'unattributed', 'Unattributed user'),
        (UNKNOWN_EXTERNAL_ACTOR_ID, 'unknown', 'unattributed', 'Unattributed external actor'),
        (UNKNOWN_ACTOR_ID, 'unknown', 'unattributed', 'Unattributed actor'),
    ]
    account_rows = con.execute("SELECT DISTINCT account_id FROM events UNION SELECT DISTINCT account_id FROM memories UNION SELECT DISTINCT account_id FROM revision_proposals").fetchall()
    for account_row in account_rows:
        for participant_id, participant_type, identity_source, display_name in builtins:
            con.execute(
                """INSERT INTO participants
                   (account_id,participant_id,participant_type,identity_source,display_name,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(account_id,participant_id) DO UPDATE SET
                     participant_type=excluded.participant_type,
                     identity_source=excluded.identity_source,
                     display_name=excluded.display_name,
                     updated_at=excluded.updated_at""",
                (account_row['account_id'], participant_id, participant_type,
                 identity_source, display_name, stamp, stamp)
            )
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
    revision_cols = {r['name'] for r in con.execute('PRAGMA table_info(revision_proposals)').fetchall()}
    if 'source_relative_path' not in revision_cols:
        con.execute('ALTER TABLE revision_proposals ADD COLUMN source_relative_path TEXT')
    if 'source_byte_length' not in revision_cols:
        con.execute('ALTER TABLE revision_proposals ADD COLUMN source_byte_length INTEGER')
    mem_event_cols = {r['name'] for r in con.execute('PRAGMA table_info(memory_events)').fetchall()}
    for col in ('from_stage','to_stage','from_usage_status','to_usage_status'):
        if col not in mem_event_cols:
            con.execute(f'ALTER TABLE memory_events ADD COLUMN {col} TEXT')
    con.commit()
    return con
