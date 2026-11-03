"""AEL context projection, hydration, packing and provider-input construction."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from math import ceil
from typing import Any
from .ledger import scope_events
from .branches import branch_statuses, branch_usage_statuses
from .memory import list_memories
from .config import now

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
