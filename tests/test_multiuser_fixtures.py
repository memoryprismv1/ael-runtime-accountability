import csv
import tempfile
import unittest
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import runtime
from ael.participant_fixtures import import_participants_csv
from ael.multiuser_fixtures import run_workflow_csv


FIXTURE = ROOT / "examples" / "multi-user-workflow"


class CSVParticipantFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.con = runtime.connect(self.root / "multiuser.sqlite3")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_roster_import_is_idempotent_and_does_not_create_membership(self):
        first = import_participants_csv(
            self.con, FIXTURE / "participants.csv", account="fixture-account"
        )
        second = import_participants_csv(
            self.con, FIXTURE / "participants.csv", account="fixture-account"
        )
        self.assertEqual(first["registered_count"], 6)
        self.assertEqual(second["registered_count"], 6)
        roster = {p["fixture_key"]: p for p in first["participants"]}
        self.assertEqual(roster["coordinator"]["type"], "human")
        self.assertEqual(roster["assistant"]["type"], "agent")
        self.assertEqual(roster["assistant"]["participant_type"], "ai_agent")
        self.assertFalse(first["membership_created"])
        self.assertEqual(
            self.con.execute(
                "SELECT COUNT(*) FROM participants WHERE account_id='fixture-account'"
            ).fetchone()[0],
            6,
        )
        self.assertEqual(
            self.con.execute(
                "SELECT COUNT(*) FROM participation_periods WHERE account_id='fixture-account'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            first["by_fixture_key"]["requester"],
            second["by_fixture_key"]["requester"],
        )

    def test_full_workflow_proves_presence_without_action_and_reentry(self):
        receipt = run_workflow_csv(
            self.con,
            participants_csv=FIXTURE / "participants.csv",
            workflow_csv=FIXTURE / "workflow.csv",
            account="fixture-account",
            project="multi-user-demo",
            chat="approval-workflow-demo",
        )
        exported = receipt["ledger"]
        participants = {
            p.get("metadata", {}).get("fixture_key"): p
            for p in exported["participants"]
        }
        manager = participants["manager"]
        requester = participants["requester"]
        approver = participants["approver"]
        assistant = participants["assistant"]

        self.assertEqual(receipt["participant_import"]["registered_count"], 6)
        self.assertEqual(len(receipt["steps"]), 16)
        self.assertGreater(len(receipt["manager_present_event_seqs"]), 0)
        self.assertFalse(receipt["manager_performed_actions"])
        self.assertEqual(len(manager["participation_periods"]), 1)
        self.assertEqual(manager["participation_periods"][0]["role"], "manager")
        self.assertEqual(len(requester["participation_periods"]), 2)

        manager_period = manager["participation_periods"][0]
        self.assertIsNotNone(manager_period["ended_by_event_id"])
        self.assertIsNotNone(manager_period["effective_until_seq"])
        manager_start = manager_period["effective_from_seq"]
        manager_end = manager_period["effective_until_seq"]

        before_join = runtime.participants_at_sequence(
            self.con, account="fixture-account", project="multi-user-demo",
            chat="approval-workflow-demo", event_seq=manager_start - 1,
        )
        during = runtime.participants_at_sequence(
            self.con, account="fixture-account", project="multi-user-demo",
            chat="approval-workflow-demo", event_seq=manager_start,
        )
        at_end = runtime.participants_at_sequence(
            self.con, account="fixture-account", project="multi-user-demo",
            chat="approval-workflow-demo", event_seq=manager_end,
        )
        self.assertNotIn(manager["participant_id"], {p["participant_id"] for p in before_join})
        self.assertIn(manager["participant_id"], {p["participant_id"] for p in during})
        self.assertNotIn(manager["participant_id"], {p["participant_id"] for p in at_end})

        events = exported["events"]
        selection = next(e for e in events if e["event_type"] == "branch.selected")
        proposal = next(e for e in events if e["event_type"] == "branch.proposed")
        self.assertEqual(proposal["actor_id"], assistant["participant_id"])
        self.assertEqual(selection["actor_id"], approver["participant_id"])
        self.assertEqual(selection["authority"], "user_direct")
        self.assertNotEqual(proposal["actor_id"], selection["actor_id"])

        manager_events = [e for e in events if e["actor_id"] == manager["participant_id"]]
        self.assertEqual(manager_events, [])
        # Yet the manager is included during both the branch proposal and approval.
        self.assertIn(proposal["seq"], receipt["manager_present_event_seqs"])
        self.assertIn(selection["seq"], receipt["manager_present_event_seqs"])

    def test_type_is_optional_defaults_to_human_and_agent_is_explicit(self):
        roster_csv = self.root / "typed-participants.csv"
        roster_csv.write_text(
            "fixture_key,type,identity_source,display_name,participant_id\n"
            "person,,self_generated,Default Human,\n"
            "agent,agent,provider,Named Agent,agent:fixture:typed-agent\n",
            encoding="utf-8",
        )
        result = import_participants_csv(
            self.con, roster_csv, account="typed-account"
        )
        roster = {p["fixture_key"]: p for p in result["participants"]}
        self.assertEqual(roster["person"]["type"], "human")
        self.assertEqual(roster["person"]["participant_type"], "human")
        self.assertEqual(roster["agent"]["type"], "agent")
        self.assertEqual(roster["agent"]["participant_type"], "ai_agent")

        # A roster can omit the optional type column entirely; it still defaults
        # to human for every row.
        no_type_csv = self.root / "no-type-participants.csv"
        no_type_csv.write_text(
            "fixture_key,identity_source,display_name,participant_id\n"
            "person,self_generated,Implicit Human,\n",
            encoding="utf-8",
        )
        no_type = import_participants_csv(
            self.con, no_type_csv, account="no-type-account"
        )
        self.assertEqual(no_type["participants"][0]["type"], "human")

    def test_invalid_type_is_rejected_before_any_identity_is_written(self):
        bad_csv = self.root / "bad-type-participants.csv"
        bad_csv.write_text(
            "fixture_key,type,identity_source,display_name,participant_id\n"
            "valid,,self_generated,Valid Human,\n"
            "bad,bot,provider,Invalid Type,agent:fixture:bad-type\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "type must be 'human' or 'agent'"):
            import_participants_csv(self.con, bad_csv, account="bad-type-account")
        self.assertEqual(
            self.con.execute(
                "SELECT COUNT(*) FROM participants WHERE account_id='bad-type-account'"
            ).fetchone()[0],
            0,
        )

    def test_invalid_roster_is_rejected_before_any_identity_is_written(self):
        bad_csv = self.root / "bad-participants.csv"
        bad_csv.write_text(
            "fixture_key,participant_type,identity_source,display_name,issuer,external_id\n"
            "valid,human,organisation,Valid User,org,1\n"
            "bad,human,organisation,Missing External ID,org,\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "requires issuer and external_id"):
            import_participants_csv(self.con, bad_csv, account="atomic-account")
        self.assertEqual(
            self.con.execute(
                "SELECT COUNT(*) FROM participants WHERE account_id='atomic-account'"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
