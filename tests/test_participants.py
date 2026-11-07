import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runtime


class ParticipantLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.con = runtime.connect(self.root / "participants.sqlite3")
        self.account, self.project, self.chat = "acct-multi", "project-a", "chat-a"
        self.admin = runtime.register_participant(
            self.con, account=self.account, issuer="org-example",
            external_id="admin-1", identity_source="organisation",
            participant_type="human", display_name="Administrator"
        )["participant_id"]

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def register(self, external_id, name):
        return runtime.register_participant(
            self.con, account=self.account, issuer="org-example",
            external_id=external_id, identity_source="organisation",
            participant_type="human", display_name=name
        )

    def test_organisation_identity_is_namespaced_and_display_name_is_not_identity(self):
        first = self.register("user-7", "Alex Smith")
        same = self.register("user-7", "Alex S.")
        other = self.register("user-8", "Alex Smith")
        self.assertEqual(first["participant_id"], "org:org-example:user-7")
        self.assertEqual(first["participant_id"], same["participant_id"])
        self.assertNotEqual(first["participant_id"], other["participant_id"])
        self.assertEqual(same["display_name"], "Alex S.")
        self.assertEqual(self.con.execute(
            "SELECT COUNT(*) FROM participants WHERE account_id=? AND participant_id=?",
            (self.account, first["participant_id"])
        ).fetchone()[0], 1)

    def test_participation_periods_are_half_open_and_support_reentry(self):
        member = self.register("manager-2", "Morgan")
        pid = member["participant_id"]

        first = runtime.join_participant(
            self.con, account=self.account, project=self.project, chat=self.chat,
            participant_id=pid, role="manager", actor_id=self.admin
        )
        start_seq = first["effective_from_seq"]
        before = start_seq - 1
        self.assertEqual(
            runtime.participants_at_sequence(self.con, account=self.account,
                project=self.project, chat=self.chat, event_seq=before), []
        )
        self.assertEqual(
            [p["participant_id"] for p in runtime.participants_at_sequence(
                self.con, account=self.account, project=self.project,
                chat=self.chat, event_seq=start_seq)], [pid]
        )

        left = runtime.leave_participant(
            self.con, account=self.account, project=self.project, chat=self.chat,
            participant_id=pid, actor_id=self.admin
        )
        end_seq = left["effective_until_seq"]
        self.assertEqual(end_seq, left["effective_from_seq"] + (end_seq - left["effective_from_seq"]))
        # The leave event itself remains inside the period; the next event is outside.
        leave_event = self.con.execute(
            "SELECT seq FROM events WHERE event_id=?", (left["ended_by_event_id"],)
        ).fetchone()["seq"]
        self.assertEqual(end_seq, leave_event + 1)
        self.assertTrue(any(p["participant_id"] == pid for p in runtime.participants_at_sequence(
            self.con, account=self.account, project=self.project, chat=self.chat,
            event_seq=leave_event)))
        self.assertEqual(runtime.participants_at_sequence(
            self.con, account=self.account, project=self.project, chat=self.chat,
            event_seq=end_seq), [])

        second = runtime.join_participant(
            self.con, account=self.account, project=self.project, chat=self.chat,
            participant_id=pid, role="approver", actor_id=self.admin
        )
        self.assertEqual(second["role"], "approver")
        periods = self.con.execute(
            "SELECT * FROM participation_periods WHERE participant_id=? ORDER BY effective_from_seq",
            (pid,)
        ).fetchall()
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0]["role"], "manager")
        self.assertEqual(periods[1]["role"], "approver")
        self.assertIsNotNone(periods[0]["effective_until_seq"])
        self.assertIsNone(periods[1]["effective_until_seq"])

    def test_branch_proposal_and_selection_have_separate_actors(self):
        proposer = self.register("proposer-1", "Priya")["participant_id"]
        decider = self.register("decider-1", "Sam")["participant_id"]
        runtime.propose_branch(
            self.con, account=self.account, project=self.project, chat=self.chat,
            branch_id="branch-1", label="Path A", tradeoff="Takes longer",
            strategy_key="path-a", actor_id=proposer
        )
        runtime.decide_branch(
            self.con, account=self.account, project=self.project, chat=self.chat,
            branch_id="branch-1", status="selected", note="Choose Path A",
            actor_id=decider
        )
        events = runtime.scope_events(self.con, self.account, self.project, self.chat)
        proposed = next(e for e in events if e["event_type"] == "branch.proposed")
        selected = next(e for e in events if e["event_type"] == "branch.selected")
        self.assertEqual(proposed["actor_id"], proposer)
        self.assertEqual(selected["actor_id"], decider)
        self.assertEqual(selected["authority"], "user_direct")
        self.assertEqual(selected["recorded_by_id"], runtime.SYSTEM_ACTOR_ID)

    def test_unregistered_explicit_actor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be registered"):
            runtime.append_event(
                self.con, account=self.account, project=self.project, chat=self.chat,
                event_type="decision", provenance="user", content="Unattributed typo",
                actor_id="org:org-example:typo-user"
            )

    def test_scope_ledger_contains_participants_and_all_periods(self):
        member = self.register("observer-3", "Taylor")["participant_id"]
        runtime.join_participant(
            self.con, account=self.account, project=self.project, chat=self.chat,
            participant_id=member, role="observer", actor_id=self.admin
        )
        exported = runtime.scope_ledger(self.con, self.account, self.project, self.chat)
        self.assertEqual(exported["schema_version"], 3)
        self.assertIn("participants", exported)
        item = next(p for p in exported["participants"] if p["participant_id"] == member)
        self.assertEqual(len(item["participation_periods"]), 1)
        self.assertEqual(item["participation_periods"][0]["role"], "observer")
        self.assertTrue(all("actor_id" in e and "recorded_by_id" in e for e in exported["events"]))

    def test_legacy_database_migration_adds_attribution_without_guessing(self):
        legacy_path = self.root / "legacy.sqlite3"
        old_schema = runtime.SCHEMA
        for fragment in (
            "  actor_id TEXT NOT NULL DEFAULT 'ael:actor:unattributed',\n",
            "  on_behalf_of_id TEXT,\n",
            "  recorded_by_id TEXT NOT NULL DEFAULT 'ael:system:runtime',\n",
        ):
            old_schema = old_schema.replace(fragment, "")
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript(old_schema)
        legacy.execute(
            """INSERT INTO events(event_id,created_at,account_id,project_id,chat_id,event_type,
               provenance,authority,inference_kind,truth_status,content)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            ("legacy-1", "2026-01-01T00:00:00Z", self.account, self.project, self.chat,
             "observation", "user", "none", "user_statement", "unverified", "Old event")
        )
        legacy.commit()
        legacy.close()

        migrated = runtime.connect(legacy_path)
        try:
            row = migrated.execute("SELECT actor_id,recorded_by_id FROM events WHERE event_id='legacy-1'").fetchone()
            self.assertEqual(row["actor_id"], runtime.UNKNOWN_ACTOR_ID)
            self.assertEqual(row["recorded_by_id"], runtime.SYSTEM_ACTOR_ID)
            actor = migrated.execute(
                "SELECT participant_type,identity_source FROM participants WHERE account_id=? AND participant_id=?",
                (self.account, runtime.UNKNOWN_ACTOR_ID)
            ).fetchone()
            self.assertEqual(actor["identity_source"], "unattributed")
        finally:
            migrated.close()


if __name__ == "__main__":
    unittest.main()
