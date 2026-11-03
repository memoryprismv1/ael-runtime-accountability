"""Disposable per-chat runtime context lifecycle."""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from .config import new_id
from .context import hydrate_payload
from .branches import decide_branch
from .revisions import decide_revision, revision_replan_context

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
