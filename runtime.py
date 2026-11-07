#!/usr/bin/env python3
"""Backward-compatible entry point for the modular AEL runtime."""
from ael.config import *
from ael.database import SCHEMA, connect
from ael.ledger import *
from ael.branches import *
from ael.memory import *
from ael.context import *
from ael.context_interventions import *
from ael.provider import *
from ael.sessions import *
from ael.checkpoints import *
from ael.revisions import *
from ael.memory import _append_memory_event, _resolution_target
from ael.context import _event_priority, _format_context_event
from ael.provider import _validate_loopback_ollama_origin
from ael.revisions import (
    _revision_payload_hash, _get_revision, _revision_state, _append_revision_event,
    _markdown_section_blocks, _resolve_declared_sections,
)  # compatibility for existing runtime callers
from ael.paths import *
from ael.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
