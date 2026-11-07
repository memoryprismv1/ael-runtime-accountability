"""AEL memory lifecycle, review, disposition and retrieval."""
from __future__ import annotations
import json
import sqlite3
from typing import Any
from .config import new_id, now, VALID_USAGE_STATUSES, UNKNOWN_USER_ACTOR_ID, UNKNOWN_ACTOR_ID, SYSTEM_ACTOR_ID

def _append_memory_event(con: sqlite3.Connection, *, memory_id: str, event_type: str,
                         from_state: str | None, to_state: str, from_stage: str | None,
                         to_stage: str, action_origin: str, note: str = '',
                         from_usage_status: str | None = None, to_usage_status: str | None = None,
                         actor_id: str | None = None, on_behalf_of_id: str | None = None,
                         recorded_by_id: str = SYSTEM_ACTOR_ID) -> None:
    # Append a traceable memory lifecycle event; history rows are immutable.
    resolved_actor = actor_id or (UNKNOWN_USER_ACTOR_ID if action_origin == 'user' else UNKNOWN_ACTOR_ID if action_origin == 'external' else SYSTEM_ACTOR_ID)
    con.execute("""INSERT INTO memory_events(memory_id,occurred_at,event_type,from_state,to_state,from_stage,to_stage,from_usage_status,to_usage_status,action_origin,note,actor_id,on_behalf_of_id,recorded_by_id)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (memory_id, now(), event_type, from_state, to_state, from_stage, to_stage, from_usage_status, to_usage_status, action_origin, note, resolved_actor, on_behalf_of_id, recorded_by_id))
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
