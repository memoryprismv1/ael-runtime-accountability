#!/usr/bin/env python3
"""Backward-compatible entry point for the modular AEL runtime."""
from ael.config import *
from ael.database import SCHEMA, connect
from ael.ledger import *
from ael.branches import *
from ael.memory import *
from ael.context import *
from ael.provider import *
from ael.sessions import *
from ael.checkpoints import *
from ael.revisions import *
from ael.paths import *
from ael.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
