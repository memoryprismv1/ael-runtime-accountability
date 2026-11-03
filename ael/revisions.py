"""Delta-first artifact revision workflow and conformance checks."""
from __future__ import annotations
import difflib
import hashlib
import json
import sqlite3
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from .config import new_id, now
from .ledger import append_event
from .context import hydrate_payload
from .paths import read_workspace_artifact, WorkspaceArtifactError

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
                     parent_revision_id: str | None = None,
                     _source_relative_path: str | None = None,
                     _source_byte_length: int | None = None) -> dict:
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
        _source_relative_path = (_source_relative_path if _source_relative_path is not None
                                 else parent.get('source_relative_path'))
        _source_byte_length = (_source_byte_length if _source_byte_length is not None
                               else parent.get('source_byte_length'))
    if not isinstance(original_request, str) or not original_request.strip():
        raise ValueError('original_request must be non-empty for a new revision proposal')
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise ValueError('artifact_id must be non-empty')
    if not isinstance(base_version, str) or not base_version.strip():
        raise ValueError('base_version must be non-empty')
    if _source_relative_path is not None:
        portable_source_path = _source_relative_path.replace(chr(92), '/')
        if (not isinstance(_source_relative_path, str) or not portable_source_path.strip()
                or PurePosixPath(portable_source_path).is_absolute()
                or PureWindowsPath(_source_relative_path).drive
                or '..' in PurePosixPath(portable_source_path).parts):
            raise ValueError('source path must be a normalized workspace-relative path')
        if not isinstance(base_sha256, str) or not base_sha256.strip():
            raise ValueError('a rooted source path requires its runtime-computed base SHA-256')
        if not isinstance(_source_byte_length, int) or _source_byte_length < 0:
            raise ValueError('a rooted source path requires its runtime-computed byte length')
    elif _source_byte_length is not None:
        raise ValueError('source byte length cannot be stored without a rooted source path')

    payload = {
      'account_id': account, 'project_id': project, 'chat_id': chat, 'proposal_id': proposal_id,
      'artifact_id': artifact_id, 'base_version': base_version, 'base_sha256': base_sha256,
      'original_request': original_request, 'delta_summary': delta_summary, 'impact_summary': impact_summary,
      'changed_sections': sections, 'parent_revision_id': parent_revision_id, 'source_ref': source_ref,
      'source_relative_path': _source_relative_path, 'source_byte_length': _source_byte_length
    }
    fingerprint = _revision_payload_hash(payload)
    con.execute('''INSERT INTO revision_proposals(proposal_id,account_id,project_id,chat_id,artifact_id,base_version,
      base_sha256,original_request,delta_summary,impact_summary,changed_sections_json,parent_revision_id,proposal_hash,
      source_ref,source_relative_path,source_byte_length,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (proposal_id, account, project, chat, artifact_id, base_version, base_sha256, original_request,
       delta_summary, impact_summary, json.dumps(sections, ensure_ascii=False), parent_revision_id,
       fingerprint, source_ref, _source_relative_path, _source_byte_length, now()))
    con.commit()
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    _append_revision_event(con, proposal=proposal, event_type='revision.proposed', from_state=None,
                           to_state='proposed', action_origin='assistant',
                           note='Structural delta proposed; full artifact has not been expanded.',
                           metadata={'parent_revision_id': parent_revision_id, 'source_ref': source_ref,
                                     'source_relative_path': _source_relative_path,
                                     'source_sha256': base_sha256 if _source_relative_path else None,
                                     'source_byte_length': _source_byte_length})
    return revision_preview(con, proposal_id, account=account, project=project, chat=chat)


def propose_revision_from_file(con, *, workspace_root: str | Path, source_path: str | Path, **proposal_args) -> dict:
    """Propose a revision from a source file read and hashed by the shared runtime."""
    if '_source_relative_path' in proposal_args or '_source_byte_length' in proposal_args:
        raise ValueError('Rooted source metadata is computed by the runtime, not supplied by callers')
    source = read_workspace_artifact(workspace_root, source_path)
    asserted_hash = proposal_args.pop('base_sha256', None)
    if asserted_hash is not None and asserted_hash != source['sha256']:
        raise ValueError('Caller-supplied base SHA-256 does not match the runtime-read source bytes')
    preview = propose_revision(
        con, base_sha256=source['sha256'],
        _source_relative_path=source['relative_path'],
        _source_byte_length=source['byte_length'], **proposal_args
    )
    preview['source_provenance'] = {
        'relative_path': source['relative_path'], 'sha256': source['sha256'],
        'byte_length': source['byte_length'], 'validation': 'pinned'
    }
    return preview


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
      'source_ref': proposal['source_ref'],
      'source_relative_path': proposal.get('source_relative_path'),
      'source_byte_length': proposal.get('source_byte_length'),
      'created_at': proposal['created_at'],
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
                    chat: str | None = None, current_base_sha256: str | None = None,
                    source_provenance: dict | None = None) -> dict:
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
                                     'base_hash_checked': proposal['base_sha256'] is not None,
                                     'source_provenance': source_provenance})
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
            'source_provenance': source_provenance, 'full_artifact_persisted': True}


def _record_source_validation_failure(con, proposal: dict, *, validation: str,
                                      observed_sha256: str | None = None, error: str = '') -> dict:
    """Retain a failed rooted-source check without changing the accepted proposal state."""
    state = _revision_state(con, proposal['proposal_id'])
    metadata = {
        'source_relative_path': proposal.get('source_relative_path'),
        'expected_sha256': proposal.get('base_sha256'),
        'observed_sha256': observed_sha256,
        'validation': validation, 'error': error, 'failed_closed': True,
    }
    return _append_revision_event(
        con, proposal=proposal, event_type='revision.source_validation_failed',
        from_state=state, to_state=state, action_origin='system',
        note=error or 'Pinned source artifact failed runtime validation.',
        metadata=metadata,
    )


def expand_revision_from_file(con, proposal_id: str, *, workspace_root: str | Path,
                              artifact_version: str, content: str,
                              account: str | None = None, project: str | None = None,
                              chat: str | None = None) -> dict:
    """Expand an accepted revision only if its pinned workspace file still matches."""
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    if _revision_state(con, proposal_id) != 'accepted_for_expansion':
        raise ValueError('File-backed expansion requires an accepted revision proposal')
    relative_path = proposal.get('source_relative_path')
    if not relative_path or not proposal.get('base_sha256'):
        raise ValueError('Revision proposal has no runtime-pinned workspace source')
    try:
        source = read_workspace_artifact(workspace_root, relative_path)
    except (WorkspaceArtifactError, OSError) as exc:
        _record_source_validation_failure(con, proposal, validation='unavailable', error=str(exc))
        raise ValueError(f'Pinned source artifact is unavailable or unsafe: {exc}') from exc
    provenance = {
        'relative_path': relative_path, 'sha256': source['sha256'],
        'byte_length': source['byte_length'],
        'validation': 'matched' if source['sha256'] == proposal['base_sha256'] else 'mismatch'
    }
    if source['sha256'] != proposal['base_sha256']:
        _record_source_validation_failure(
            con, proposal, validation='mismatch', observed_sha256=source['sha256'],
            error='Pinned source artifact changed after proposal review; expansion refused.'
        )
        raise ValueError('Pinned source artifact changed after proposal review; create a fresh proposal')
    return expand_revision(
        con, proposal_id, artifact_version=artifact_version, content=content,
        account=account, project=project, chat=chat,
        current_base_sha256=source['sha256'], source_provenance=provenance
    )



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
                           chat: str | None = None,
                           source_provenance: dict | None = None) -> dict:
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

    if source_provenance is not None:
        report['source_provenance'] = source_provenance
    return _store_revision_verification(con, proposal, output, report, computed_base_hash)


def _store_revision_verification(con, proposal: dict, output: dict, report: dict,
                                  computed_base_hash: str | None) -> dict:
    """Persist one immutable conformance result and its lifecycle consequence."""
    proposal_id = proposal['proposal_id']
    status = report['status'] if report['status'] in {'pass', 'fail', 'unverifiable'} else 'fail'
    check_id = new_id('CONF')
    con.execute('''INSERT INTO revision_conformance_checks(check_id,proposal_id,proposal_hash,base_sha256,output_sha256,status,report_json,created_at)
      VALUES(?,?,?,?,?,?,?,?)''', (check_id, proposal_id, proposal['proposal_hash'], computed_base_hash,
       output['content_sha256'], status, json.dumps(report, ensure_ascii=False, sort_keys=True), now()))
    con.commit()
    source_meta = {'source_provenance': report['source_provenance']} if report.get('source_provenance') else {}
    if report.get('passed'):
        _append_revision_event(con, proposal=proposal, event_type='revision.conformance_passed',
                               from_state='expanded', to_state='expanded', action_origin='system',
                               note='Output stays within the approved changed-section scope.',
                               metadata={'check_id': check_id, 'output_sha256': output['content_sha256'], **source_meta})
    else:
        correction = '; '.join(report.get('selector_problems', []) +
                               ([f"Changes outside approved scope: {', '.join(report['undeclared_changes'])}"] if report.get('undeclared_changes') else []) +
                               ([f"Declared sections not changed: {', '.join(report['declared_but_unchanged'])}"] if report.get('declared_but_unchanged') else []))
        _append_revision_event(con, proposal=proposal, event_type='revision.conformance_failed',
                               from_state='expanded', to_state='rejected_reset', action_origin='system',
                               note=correction or 'Artifact did not conform to its accepted delta; reset and re-plan.',
                               metadata={'check_id': check_id, 'output_sha256': output['content_sha256'],
                                         'failed_closed': True, **source_meta})
        append_event(con, account=proposal['account_id'], project=proposal['project_id'], chat=proposal['chat_id'],
                     event_type='revision.conformance_failed', provenance='system', authority='system_process',
                     inference_kind='process_event', truth_status='not_applicable',
                     source_ref=f'revision-conformance:{check_id}',
                     content=correction or 'Expanded artifact did not conform to its accepted delta; a fresh proposal is required.',
                     metadata={'proposal_id': proposal_id, 'proposal_hash': proposal['proposal_hash'],
                               'check_id': check_id, **source_meta})
    report.update({'check_id': check_id, 'proposal_id': proposal_id, 'proposal_hash': proposal['proposal_hash'],
                   'output_id': output['output_id'], 'status': status, 'passed': bool(report.get('passed')),
                   'ready_for_release': bool(report.get('passed'))})
    return report


def verify_revision_output_from_file(con, proposal_id: str, *, workspace_root: str | Path,
                                     account: str | None = None, project: str | None = None,
                                     chat: str | None = None) -> dict:
    """Verify an expanded output against the exact rooted source pinned at proposal time."""
    proposal = _get_revision(con, proposal_id, account=account, project=project, chat=chat)
    if _revision_state(con, proposal_id) != 'expanded':
        raise ValueError('File-backed verification requires an expanded revision')
    relative_path = proposal.get('source_relative_path')
    if not relative_path or not proposal.get('base_sha256'):
        raise ValueError('Revision proposal has no runtime-pinned workspace source')
    output_row = con.execute('SELECT * FROM revision_outputs WHERE proposal_id=? ORDER BY created_at DESC LIMIT 1',
                              (proposal_id,)).fetchone()
    if not output_row:
        raise ValueError(f'No expanded artifact exists for revision {proposal_id!r}')
    output = dict(output_row)
    try:
        source = read_workspace_artifact(workspace_root, relative_path)
    except (WorkspaceArtifactError, OSError) as exc:
        provenance = {
            'relative_path': relative_path, 'sha256': None, 'byte_length': None,
            'validation': 'unavailable', 'error': str(exc)
        }
        report = {
            'schema_version': 1, 'base_sha256': None,
            'expected_base_sha256': proposal['base_sha256'],
            'candidate_sha256': output['content_sha256'],
            'declared_changed_sections': list(proposal['changed_sections']),
            'actual_changed_sections': [], 'undeclared_changes': [],
            'declared_but_unchanged': [],
            'selector_problems': [f'Pinned source artifact could not be re-read: {exc}'],
            'added_line_count': 0, 'removed_line_count': 0,
            'status': 'unverifiable', 'passed': False,
            'limits': ['The pinned workspace source was unavailable, so conformance could not be established.'],
            'source_provenance': provenance,
        }
        return _store_revision_verification(con, proposal, output, report, None)

    provenance = {
        'relative_path': relative_path, 'sha256': source['sha256'],
        'byte_length': source['byte_length'],
        'validation': 'matched' if source['sha256'] == proposal['base_sha256'] else 'mismatch'
    }
    return verify_revision_output(
        con, proposal_id, base_content=source['content'],
        account=account, project=project, chat=chat,
        source_provenance=provenance
    )


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
