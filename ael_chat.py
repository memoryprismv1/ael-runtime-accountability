#!/usr/bin/env python3
"""Interactive AEL chat through a locally installed Ollama model; no paid API key."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import runtime

ROOT = Path(__file__).resolve().parent


def safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned[:80] or "chat"


def select_model(available: list[str], requested: str | None) -> str:
    if not available:
        raise RuntimeError(
            "Ollama is responding, but no local models are installed. "
            "Choose a model suitable for your computer and install it with `ollama pull <model-tag>`."
        )
    if requested:
        if requested.casefold().endswith(":cloud"):
            raise RuntimeError("This bridge is local-only; cloud models are refused.")
        if requested not in available:
            raise RuntimeError(
                f"Model {requested!r} is not listed as locally installed. Available local models: "
                + ", ".join(available)
            )
        return requested
    if len(available) == 1:
        return available[0]
    print("Installed local models:")
    for i, name in enumerate(available, 1):
        print(f"  {i}. {name}")
    answer = input("Choose model number (default 1): ").strip()
    if not answer:
        return available[0]
    if answer.isdigit() and 1 <= int(answer) <= len(available):
        return available[int(answer) - 1]
    if answer in available:
        return answer
    raise RuntimeError("Model selection did not match the displayed local models.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Interactive chat using AEL's local history/context runtime and a loopback-only Ollama model."
    )
    p.add_argument("--db", help="SQLite event ledger (default: stable per-user AEL data directory)")
    p.add_argument("--account", default="default")
    p.add_argument("--project", default="general", help="Project scope for this conversation")
    p.add_argument("--chat", help="Reuse this chat ID; otherwise a fresh one is created")
    p.add_argument("--model", help="Exact model name shown by Ollama's local model list")
    p.add_argument("--endpoint", default="http://127.0.0.1:11434", help="Loopback Ollama endpoint")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--max-tokens", type=int, default=12000)
    p.add_argument("--recent-assistant-turns", type=int, default=6)
    p.add_argument("--relevance-tags", nargs="*", help="Memory tags explicitly applicable to this task")
    p.add_argument("--audit-dir", help="Directory for per-turn local audit sidecars (default: alongside the per-user database)")
    args = p.parse_args(argv)

    try:
        status = runtime.ollama_status(args.endpoint, timeout=min(args.timeout, 5.0))
    except ValueError as exc:
        print(f"Blocked unsafe endpoint: {exc}", file=sys.stderr)
        return 2
    if not status.get("available"):
        print(status.get("error", "Local Ollama is unavailable."), file=sys.stderr)
        print("Install/start Ollama on this computer, then run this launcher again.", file=sys.stderr)
        print("Official download: https://ollama.com/download/windows", file=sys.stderr)
        return 2
    try:
        model = select_model(status.get("local_models", []), args.model)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    data_dir = runtime.default_data_dir()
    db_path = Path(args.db).expanduser() if args.db else data_dir / "ael.sqlite3"
    if args.db and not db_path.is_absolute():
        db_path = ROOT / db_path
    audit_root = Path(args.audit_dir).expanduser() if args.audit_dir else data_dir / "audit"
    if args.audit_dir and not audit_root.is_absolute():
        audit_root = ROOT / audit_root
    chat_id = args.chat or f"chat-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    print("AEL local chat is ready.")
    print(f"Model: {model} | Project: {args.project} | Chat: {chat_id}")
    print("Local Ollama only. No paid API key. Type /new for a clean chat, /help for commands, or /quit to exit.")

    turn = 0
    while True:
        try:
            message = input("you> ")
        except (EOFError, KeyboardInterrupt):
            print("\nChat ended. Your conversation remains in the local ledger.")
            return 0
        message = message.strip()
        if not message:
            continue
        if message.casefold() in {"/quit", "/exit", ":q"}:
            print("Chat ended. Your conversation remains in the local ledger.")
            return 0
        if message.casefold() == "/help":
            print("Commands: /new (start a new isolated chat), /status (show current scope), /quit (exit).")
            continue
        if message.casefold() == "/status":
            print(f"Model: {model} | Project: {args.project} | Chat: {chat_id}")
            print(f"Database: {db_path}")
            continue
        if message.casefold() == "/new":
            chat_id = f"chat-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            turn = 0
            print(f"New isolated chat: {chat_id}")
            continue

        turn += 1
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        chat_dir = audit_root / safe_component(chat_id)
        chat_dir.mkdir(parents=True, exist_ok=True)
        audit_path = chat_dir / f"turn-{turn:04d}-{stamp}.json"
        with tempfile.TemporaryDirectory(prefix="ael-local-response-") as temp_dir:
            response_path = Path(temp_dir) / "response.json"
            cmd = [
                sys.executable, str(ROOT / "runtime.py"), "--db", str(db_path), "--account", args.account,
                "ollama-chat", "--project", args.project, "--chat", chat_id,
                "--current-user-message", message, "--model", model, "--endpoint", args.endpoint,
                "--timeout", str(args.timeout), "--max-tokens", str(args.max_tokens),
                "--recent-assistant-turns", str(args.recent_assistant_turns),
                "--out", str(response_path), "--audit-out", str(audit_path),
            ]
            if args.relevance_tags is not None:
                cmd.append("--relevance-tags")
                cmd.extend(args.relevance_tags)
            completed = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=args.timeout + 15)
            if completed.returncode != 0:
                lines = [line for line in completed.stderr.splitlines() if line.strip()]
                detail = lines[-1] if lines else "local model call failed"
                print(f"AEL call failed: {detail}", file=sys.stderr)
                if audit_path.exists():
                    print(f"Local audit: {audit_path}", file=sys.stderr)
                continue
            try:
                result = json.loads(response_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"AEL returned an unreadable response record: {exc}", file=sys.stderr)
                continue
            print(f"chatty> {result['content']}")
            print(f"[audit saved locally: {audit_path}]\n")


if __name__ == "__main__":
    raise SystemExit(main())
