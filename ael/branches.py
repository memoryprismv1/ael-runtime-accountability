"""AEL branch decisions, materiality gate and branch reuse state."""
from __future__ import annotations
import json
import sqlite3
from .config import now, VALID_USAGE_STATUSES, BRANCH_REUSE_STATUSES, ASSISTANT_ACTOR_ID
from .ledger import append_event

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
                   label: str, tradeoff: str, strategy_key: str, original_query: str | None = None,
                   actor_id: str | None = None) -> None:
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
                 metadata={'strategy_key': strategy_key, 'original_query': original_query},
                 actor_id=actor_id or ASSISTANT_ACTOR_ID)


def reject_branch(con, *, account='default', project: str, chat: str, branch_id: str,
                  note: str, strategy_failure: bool = False, threshold: int = 3,
                  usage_status: str = 'not_pertinent_now', actor_id: str | None = None) -> dict:
    b = con.execute('''SELECT * FROM branches WHERE branch_id=? AND account_id=? AND project_id=? AND chat_id=?''',
                    (branch_id, account, project, chat)).fetchone()
    if not b:
        raise ValueError(f'Unknown branch {branch_id!r} for this account/project/chat')
    if usage_status not in BRANCH_REUSE_STATUSES:
        raise ValueError(f'usage_status must be one of {sorted(BRANCH_REUSE_STATUSES)}')
    append_event(con, account=account, project=project, chat=chat, event_type='branch.rejected', provenance='user',
                 authority='user_direct', inference_kind='decision', truth_status='not_applicable',
                 content=note or 'User rejected this branch', branch_id=branch_id, actor_id=actor_id,
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
                  threshold: int = 3, usage_status: str = 'not_pertinent_now',
                  actor_id: str | None = None) -> dict | None:
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
                             note=note, strategy_failure=strategy_failure, threshold=threshold, usage_status=usage_status, actor_id=actor_id)
    authority = 'user_direct' if decision_path == 'direct' else 'user_ratified_recommendation' if decision_path == 'accepted_recommendation' else 'system_process'
    append_event(con, account=account, project=project, chat=chat, event_type=f'branch.{status}', provenance='user' if decision_path != 'system' else 'system',
                 authority=authority, inference_kind='decision', truth_status='not_applicable', content=note or f'Branch {status}',
                 branch_id=branch_id, strategy_key=b['strategy_key'], metadata={'decision_path': decision_path}, actor_id=actor_id)
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
