"""Shared runtime constants, identifiers and user data location."""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
