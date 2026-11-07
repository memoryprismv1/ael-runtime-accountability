#!/usr/bin/env python3
"""Execute the bundled CSV multi-user AEL workflow fixture."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import runtime
from ael.multiuser_fixtures import run_workflow_csv, write_receipt


def main(argv: list[str] | None = None) -> int:
    fixture_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Optional persistent SQLite path; defaults to a temporary database")
    parser.add_argument("--account", default="fixture-account")
    parser.add_argument("--project", default="multi-user-demo")
    parser.add_argument("--chat", default="approval-workflow-demo")
    parser.add_argument("--participants", default=str(fixture_dir / "participants.csv"))
    parser.add_argument("--workflow", default=str(fixture_dir / "workflow.csv"))
    parser.add_argument("--out", default=str(ROOT / "handoffs" / "multi-user-fixture-receipt.json"))
    args = parser.parse_args(argv)

    temporary_db = tempfile.TemporaryDirectory(prefix="ael-multiuser-fixture-") if not args.db else None
    db_path = args.db or str(Path(temporary_db.name) / "fixture.sqlite3")
    con = runtime.connect(db_path)
    try:
        receipt = run_workflow_csv(
            con,
            participants_csv=args.participants,
            workflow_csv=args.workflow,
            account=args.account,
            project=args.project,
            chat=args.chat,
        )
        path = write_receipt(receipt, args.out)
        print(json.dumps({
            "completed": True,
            "registered_participants": receipt["participant_import"]["registered_count"],
            "workflow_steps": len(receipt["steps"]),
            "ledger_events": receipt["last_event_seq"],
            "manager_present_event_count": len(receipt["manager_present_event_seqs"]),
            "manager_performed_actions": receipt["manager_performed_actions"],
            "requester_participation_periods": next(
                len(p["participation_periods"]) for p in receipt["ledger"]["participants"]
                if p.get("metadata", {}).get("fixture_key") == "requester"
            ),
            "receipt": str(path),
        }, ensure_ascii=False, indent=2))
    finally:
        con.close()
        if temporary_db:
            temporary_db.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
