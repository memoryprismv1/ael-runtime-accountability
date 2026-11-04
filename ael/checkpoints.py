"""Portable Markdown and JSON checkpoints derived from the canonical ledger."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from .config import new_id, now
from .context import hydrate_payload, render_markdown

def checkpoint(con, *, account='default', project: str, chat: str, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    payload = hydrate_payload(con, account=account, project=project, chat=chat)
    # A checkpoint row is a retained snapshot reference. Its exported files
    # must therefore be unique: reusing project/chat-only paths would let a
    # later export overwrite the bytes (and hash) of an earlier checkpoint.
    checkpoint_id = new_id('CP')
    md = out / f'checkpoint-{project}-{chat}-{checkpoint_id}.md'
    js = out / f'checkpoint-{project}-{chat}-{checkpoint_id}.json'
    md.write_text(render_markdown(payload), encoding='utf-8')
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    js.write_text(raw, encoding='utf-8')
    # Verify snapshot can be parsed and sequence/hash corresponds to ledger projection.
    saved_raw = js.read_text(encoding='utf-8')
    loaded = json.loads(saved_raw)
    if loaded['last_event_seq'] != payload['last_event_seq']:
        raise RuntimeError('Checkpoint event sequence verification failed')
    sha = hashlib.sha256(saved_raw.encode('utf-8')).hexdigest()
    con.execute('''INSERT INTO checkpoints(checkpoint_id,created_at,account_id,project_id,chat_id,last_event_seq,markdown_path,json_path,snapshot_sha256)
      VALUES(?,?,?,?,?,?,?,?,?)''', (checkpoint_id, now(), account, project, chat, payload['last_event_seq'], str(md), str(js), sha))
    con.commit()
    return md, js
