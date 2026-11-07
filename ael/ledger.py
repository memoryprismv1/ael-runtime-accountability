"""Canonical, append-only AEL event ledger and participant registry."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .config import (
    new_id, now, VALID_PROVENANCE, VALID_AUTHORITIES,
    VALID_INFERENCE_KINDS, VALID_TRUTH_STATUSES,
    VALID_PARTICIPANT_TYPES, VALID_IDENTITY_SOURCES,
    UNKNOWN_USER_ACTOR_ID, UNKNOWN_EXTERNAL_ACTOR_ID,
    UNKNOWN_ACTOR_ID, ASSISTANT_ACTOR_ID, SYSTEM_ACTOR_ID,
)

DEFAULT_ACTOR_BY_PROVENANCE = {
    'user': UNKNOWN_USER_ACTOR_ID,
    'assistant': ASSISTANT_ACTOR_ID,
    'external': UNKNOWN_EXTERNAL_ACTOR_ID,
    'system': SYSTEM_ACTOR_ID,
}


def register_participant(
    con: sqlite3.Connection, *, account='default', participant_id: str | None = None,
    participant_type: str = 'human', identity_source: str = 'self_generated',
    display_name: str = '', issuer: str | None = None, external_id: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Register one stable identity. Display names are descriptive, never keys."""
    if participant_type not in VALID_PARTICIPANT_TYPES:
        raise ValueError(f'participant_type must be one of {sorted(VALID_PARTICIPANT_TYPES)}')
    if identity_source not in VALID_IDENTITY_SOURCES:
        raise ValueError(f'identity_source must be one of {sorted(VALID_IDENTITY_SOURCES)}')
    if identity_source == 'organisation':
        if not issuer or not external_id:
            raise ValueError('Organisation identities require both issuer and external_id')
        canonical_id = f'org:{issuer}:{external_id}'
        if participant_id is not None and participant_id != canonical_id:
            raise ValueError('Organisation participant_id must match org:<issuer>:<external_id>')
        participant_id = canonical_id
    elif identity_source == 'self_generated':
        if issuer is not None or external_id is not None:
            raise ValueError('Self-generated identities cannot carry organisation issuer/external_id fields')
        participant_id = participant_id or f'ael:participant:{new_id("ID").lower()}'
    elif not participant_id:
        raise ValueError('participant_id is required for provider, system or unattributed identities')
    if not participant_id or not isinstance(participant_id, str) or not participant_id.strip():
        raise ValueError('participant_id must be a non-empty string')

    existing = con.execute(
        'SELECT * FROM participants WHERE account_id=? AND participant_id=?',
        (account, participant_id)
    ).fetchone()
    if existing:
        if (existing['participant_type'] != participant_type
                or existing['identity_source'] != identity_source
                or existing['issuer'] != issuer
                or existing['external_id'] != external_id):
            raise ValueError('participant_id is already registered with a different identity definition')
        if display_name and display_name != existing['display_name']:
            con.execute(
                'UPDATE participants SET display_name=?,updated_at=? WHERE account_id=? AND participant_id=?',
                (display_name, now(), account, participant_id)
            )
            con.commit()
        return dict(con.execute(
            'SELECT * FROM participants WHERE account_id=? AND participant_id=?',
            (account, participant_id)
        ).fetchone())

    stamp = now()
    con.execute(
        """INSERT INTO participants
           (account_id,participant_id,participant_type,identity_source,issuer,external_id,
            display_name,created_at,updated_at,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (account, participant_id, participant_type, identity_source, issuer, external_id,
         display_name or participant_id, stamp, stamp,
         json.dumps(metadata or {}, ensure_ascii=False))
    )
    con.commit()
    return dict(con.execute(
        'SELECT * FROM participants WHERE account_id=? AND participant_id=?',
        (account, participant_id)
    ).fetchone())


def _ensure_actor(con: sqlite3.Connection, *, account: str, participant_id: str,
                  participant_type: str = 'unknown', identity_source: str = 'unattributed') -> None:
    row = con.execute(
        'SELECT 1 FROM participants WHERE account_id=? AND participant_id=?',
        (account, participant_id)
    ).fetchone()
    if row:
        return
    # Only the reserved fallback actors may be created implicitly. Explicit IDs
    # must be registered first; this catches typos instead of creating identities.
    if participant_id == SYSTEM_ACTOR_ID:
        register_participant(con, account=account, participant_id=participant_id,
                             participant_type='system', identity_source='system',
                             display_name='AEL runtime')
    elif participant_id == ASSISTANT_ACTOR_ID:
        register_participant(con, account=account, participant_id=participant_id,
                             participant_type='ai_agent', identity_source='system',
                             display_name='AEL assistant agent')
    elif participant_id in {UNKNOWN_USER_ACTOR_ID, UNKNOWN_EXTERNAL_ACTOR_ID, UNKNOWN_ACTOR_ID}:
        register_participant(con, account=account, participant_id=participant_id,
                             participant_type=participant_type, identity_source=identity_source,
                             display_name=participant_id)
    else:
        raise ValueError(f'Actor must be registered before being referenced: {participant_id}')


def append_event(
    con: sqlite3.Connection, *, account='default', project: str, chat: str,
    event_type: str, provenance: str, content: str, authority='none',
    inference_kind='unspecified', truth_status='unverified', source_ref=None,
    branch_id=None, strategy_key=None, metadata: dict | None = None,
    actor_id: str | None = None, on_behalf_of_id: str | None = None,
    recorded_by_id: str = SYSTEM_ACTOR_ID,
) -> dict[str, Any]:
    """Append an immutable event with explicit actor, authority and recorder identity."""
    if provenance not in VALID_PROVENANCE:
        raise ValueError(f'provenance must be one of {sorted(VALID_PROVENANCE)}')
    if authority not in VALID_AUTHORITIES:
        raise ValueError(f'authority must be one of {sorted(VALID_AUTHORITIES)}')
    if inference_kind not in VALID_INFERENCE_KINDS:
        raise ValueError(f'inference_kind must be one of {sorted(VALID_INFERENCE_KINDS)}')
    if truth_status not in VALID_TRUTH_STATUSES:
        raise ValueError(f'truth_status must be one of {sorted(VALID_TRUTH_STATUSES)}')

    actor_id = actor_id or DEFAULT_ACTOR_BY_PROVENANCE[provenance]
    _ensure_actor(con, account=account, participant_id=actor_id)
    _ensure_actor(con, account=account, participant_id=recorded_by_id)
    if on_behalf_of_id:
        if not con.execute(
            'SELECT 1 FROM participants WHERE account_id=? AND participant_id=?',
            (account, on_behalf_of_id)
        ).fetchone():
            raise ValueError(f'on_behalf_of_id is not registered: {on_behalf_of_id}')

    eid, ts = new_id('EV'), now()
    cur = con.execute(
        """INSERT INTO events(event_id,created_at,account_id,project_id,chat_id,event_type,
           provenance,authority,inference_kind,truth_status,source_ref,content,branch_id,
           strategy_key,metadata_json,actor_id,on_behalf_of_id,recorded_by_id)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, ts, account, project, chat, event_type, provenance, authority,
         inference_kind, truth_status, source_ref, content, branch_id, strategy_key,
         json.dumps(metadata or {}, ensure_ascii=False), actor_id, on_behalf_of_id, recorded_by_id)
    )
    con.commit()
    return dict(con.execute('SELECT * FROM events WHERE seq=?', (cur.lastrowid,)).fetchone())


def scope_events(con, account: str, project: str, chat: str) -> list[dict]:
    rows = con.execute(
        'SELECT * FROM events WHERE account_id=? AND project_id=? AND chat_id=? ORDER BY seq',
        (account, project, chat)
    ).fetchall()
    return [dict(r) for r in rows]


def join_participant(
    con: sqlite3.Connection, *, account='default', project: str, chat: str,
    participant_id: str, role: str = 'participant', workflow_id: str | None = None,
    actor_id: str | None = None, note: str = '', metadata: dict | None = None,
) -> dict[str, Any]:
    """Add a participant. Membership starts on the event after participant.joined."""
    if not con.execute(
        'SELECT 1 FROM participants WHERE account_id=? AND participant_id=?',
        (account, participant_id)
    ).fetchone():
        raise ValueError(f'Participant must be registered before joining: {participant_id}')
    if not role or not role.strip():
        raise ValueError('role must be non-empty')
    active = con.execute(
        """SELECT 1 FROM participation_periods WHERE account_id=? AND project_id=? AND chat_id=?
           AND ifnull(workflow_id,'')=ifnull(?,'') AND participant_id=? AND effective_until_seq IS NULL""",
        (account, project, chat, workflow_id, participant_id)
    ).fetchone()
    if active:
        raise ValueError('Participant already has an active period in this scope')

    event = append_event(
        con, account=account, project=project, chat=chat, event_type='participant.joined',
        provenance='user', authority='user_direct', inference_kind='process_event',
        truth_status='not_applicable', actor_id=actor_id,
        content=note or f'Participant {participant_id} joined as {role}.',
        metadata={'participant_id': participant_id, 'role': role, 'workflow_id': workflow_id, **(metadata or {})}
    )
    period_id = new_id('PERIOD')
    con.execute(
        """INSERT INTO participation_periods
           (participation_period_id,account_id,project_id,chat_id,workflow_id,participant_id,
            role,started_by_event_id,effective_from_seq,created_at,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (period_id, account, project, chat, workflow_id, participant_id, role,
         event['event_id'], event['seq'] + 1, now(), json.dumps(metadata or {}, ensure_ascii=False))
    )
    con.commit()
    return dict(con.execute(
        'SELECT * FROM participation_periods WHERE participation_period_id=?', (period_id,)
    ).fetchone())


def leave_participant(
    con: sqlite3.Connection, *, account='default', project: str, chat: str,
    participant_id: str, workflow_id: str | None = None,
    actor_id: str | None = None, note: str = '', metadata: dict | None = None,
) -> dict[str, Any]:
    """End the active period; the leave event itself is within that period."""
    period = con.execute(
        """SELECT * FROM participation_periods WHERE account_id=? AND project_id=? AND chat_id=?
           AND ifnull(workflow_id,'')=ifnull(?,'') AND participant_id=? AND effective_until_seq IS NULL""",
        (account, project, chat, workflow_id, participant_id)
    ).fetchone()
    if not period:
        raise ValueError(f'No active participation period for {participant_id}')
    event = append_event(
        con, account=account, project=project, chat=chat, event_type='participant.left',
        provenance='user', authority='user_direct', inference_kind='process_event',
        truth_status='not_applicable', actor_id=actor_id,
        content=note or f'Participant {participant_id} left.',
        metadata={'participant_id': participant_id, 'role': period['role'],
                  'workflow_id': workflow_id, **(metadata or {})}
    )
    con.execute(
        """UPDATE participation_periods SET ended_by_event_id=?,effective_until_seq=?
           WHERE participation_period_id=? AND effective_until_seq IS NULL""",
        (event['event_id'], event['seq'] + 1, period['participation_period_id'])
    )
    con.commit()
    return dict(con.execute(
        'SELECT * FROM participation_periods WHERE participation_period_id=?',
        (period['participation_period_id'],)
    ).fetchone())


def participants_at_sequence(
    con: sqlite3.Connection, *, account='default', project: str, chat: str,
    event_seq: int, workflow_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return members whose half-open participation interval contains event_seq."""
    rows = con.execute(
        """SELECT p.*, pp.participation_period_id, pp.role, pp.workflow_id,
                  pp.started_by_event_id, pp.effective_from_seq,
                  pp.ended_by_event_id, pp.effective_until_seq
           FROM participation_periods pp
           JOIN participants p ON p.account_id=pp.account_id AND p.participant_id=pp.participant_id
           WHERE pp.account_id=? AND pp.project_id=? AND pp.chat_id=?
             AND (pp.workflow_id IS NULL OR pp.workflow_id=?)
             AND pp.effective_from_seq<=?
             AND (pp.effective_until_seq IS NULL OR ?<pp.effective_until_seq)
           ORDER BY p.participant_id""",
        (account, project, chat, workflow_id, event_seq, event_seq)
    ).fetchall()
    return [dict(r) for r in rows]


def scope_ledger(con: sqlite3.Connection, account: str, project: str, chat: str) -> dict[str, Any]:
    """Return the ledger format, including one participant object with all scoped periods."""
    events = scope_events(con, account, project, chat)
    ids = {e['actor_id'] for e in events}
    ids.update(e['on_behalf_of_id'] for e in events if e.get('on_behalf_of_id'))
    ids.update(e['recorded_by_id'] for e in events)
    period_rows = con.execute(
        """SELECT * FROM participation_periods WHERE account_id=? AND project_id=? AND chat_id=?
           ORDER BY effective_from_seq""", (account, project, chat)
    ).fetchall()
    ids.update(r['participant_id'] for r in period_rows)
    for row in con.execute(
        """SELECT DISTINCT re.actor_id AS participant_id FROM revision_events re
             JOIN revision_proposals rp ON rp.proposal_id=re.proposal_id
             WHERE rp.account_id=? AND rp.project_id=? AND rp.chat_id=?
             UNION SELECT DISTINCT re.recorded_by_id FROM revision_events re
             JOIN revision_proposals rp ON rp.proposal_id=re.proposal_id
             WHERE rp.account_id=? AND rp.project_id=? AND rp.chat_id=?
             UNION SELECT DISTINCT re.on_behalf_of_id FROM revision_events re
             JOIN revision_proposals rp ON rp.proposal_id=re.proposal_id
             WHERE rp.account_id=? AND rp.project_id=? AND rp.chat_id=?""",
        (account, project, chat, account, project, chat, account, project, chat)).fetchall():
        if row['participant_id']:
            ids.add(row['participant_id'])
    memory_owner_sql = """SELECT candidate_id AS memory_id,account_id,origin_project_id AS project_id,chat_id FROM memory_candidates
                          UNION ALL SELECT m.memory_id,m.account_id,e.project_id,e.chat_id
                          FROM memories m JOIN events e ON e.seq=m.source_event_seq"""
    for row in con.execute(
        f"""SELECT DISTINCT me.actor_id AS participant_id FROM memory_events me
              JOIN ({memory_owner_sql}) owner ON owner.memory_id=me.memory_id
              WHERE owner.account_id=? AND owner.project_id=? AND owner.chat_id=?
              UNION SELECT DISTINCT me.recorded_by_id FROM memory_events me
              JOIN ({memory_owner_sql}) owner ON owner.memory_id=me.memory_id
              WHERE owner.account_id=? AND owner.project_id=? AND owner.chat_id=?
              UNION SELECT DISTINCT me.on_behalf_of_id FROM memory_events me
              JOIN ({memory_owner_sql}) owner ON owner.memory_id=me.memory_id
              WHERE owner.account_id=? AND owner.project_id=? AND owner.chat_id=?""",
        (account, project, chat, account, project, chat, account, project, chat)).fetchall():
        if row['participant_id']:
            ids.add(row['participant_id'])
    participants = []
    for participant_id in sorted(ids):
        row = con.execute(
            'SELECT * FROM participants WHERE account_id=? AND participant_id=?',
            (account, participant_id)
        ).fetchone()
        if not row:
            continue
        item = dict(row)
        item['metadata'] = json.loads(item.pop('metadata_json') or '{}')
        item['participation_periods'] = [
            {k: v for k, v in dict(period).items() if k not in {'account_id','participant_id','created_at','metadata_json'}}
            | {'metadata': json.loads(period['metadata_json'] or '{}')}
            for period in period_rows if period['participant_id'] == participant_id
        ]
        participants.append(item)
    return {
        'schema_version': 3,
        'account_id': account,
        'project_id': project,
        'chat_id': chat,
        'participants': participants,
        'events': events,
        'participant_period_semantics': '[effective_from_seq, effective_until_seq); the start is included and the end is excluded.',
    }
