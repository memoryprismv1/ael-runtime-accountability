import csv
import json
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
        self.assertEqual(first["registered_count"], 8)
        self.assertEqual(second["registered_count"], 8)
        roster = {p["fixture_key"]: p for p in first["participants"]}
        self.assertEqual(roster["coordinator"]["type"], "human")
        for key in ("assistant", "reviewer", "implementer", "validator"):
            self.assertEqual(roster[key]["type"], "agent")
            self.assertEqual(roster[key]["participant_type"], "ai_agent")
        self.assertEqual(roster["requester"]["type"], "human")
        self.assertFalse(first["membership_created"])
        self.assertEqual(
            self.con.execute(
                "SELECT COUNT(*) FROM participants WHERE account_id='fixture-account'"
            ).fetchone()[0],
            8,
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
        reviewer = participants["reviewer"]
        implementer = participants["implementer"]
        validator = participants["validator"]

        self.assertEqual(receipt["participant_import"]["registered_count"], 8)
        self.assertEqual(len(receipt["steps"]), 27)
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
        by_step = {
            event.get("metadata_json") and json.loads(event["metadata_json"]).get("fixture_step"): event
            for event in events
            if event.get("metadata_json")
        }
        self.assertEqual(by_step[9]["actor_id"], requester["participant_id"])
        self.assertEqual(by_step[9]["provenance"], "user")
        self.assertEqual(by_step[9]["authority"], "user_direct")

        # Agent messages are attributed to the registered agent, not flattened
        # into user statements or given human authority.
        self.assertEqual(by_step[10]["actor_id"], assistant["participant_id"])
        self.assertEqual(by_step[10]["provenance"], "assistant")
        self.assertEqual(by_step[10]["authority"], "none")
        self.assertEqual(by_step[11]["actor_id"], reviewer["participant_id"])
        self.assertEqual(by_step[11]["provenance"], "assistant")
        self.assertEqual(by_step[16]["actor_id"], implementer["participant_id"])
        self.assertEqual(by_step[17]["actor_id"], validator["participant_id"])
        self.assertEqual(by_step[22]["actor_id"], validator["participant_id"])
        for step in (10, 11, 12, 16, 17, 21, 22):
            self.assertEqual(by_step[step]["provenance"], "assistant")
            self.assertEqual(by_step[step]["authority"], "none")

        route_a_proposal = next(
            e for e in events if e["event_type"] == "branch.proposed" and e["branch_id"] == "route-a"
        )
        route_b_proposal = next(
            e for e in events if e["event_type"] == "branch.proposed" and e["branch_id"] == "route-b"
        )
        route_c_proposal = next(
            e for e in events if e["event_type"] == "branch.proposed" and e["branch_id"] == "route-c"
        )
        self.assertEqual(route_a_proposal["actor_id"], assistant["participant_id"])
        self.assertEqual(route_b_proposal["actor_id"], reviewer["participant_id"])
        self.assertEqual(route_c_proposal["actor_id"], reviewer["participant_id"])

        route_a_decisions = [
            e for e in events if e["branch_id"] == "route-a"
            and e["event_type"] in {"branch.selected", "branch.rejected"}
        ]
        self.assertEqual([e["event_type"] for e in route_a_decisions],
                         ["branch.selected", "branch.rejected"])
        self.assertTrue(all(e["actor_id"] == approver["participant_id"] for e in route_a_decisions))
        self.assertTrue(all(e["authority"] == "user_direct" for e in route_a_decisions))
        route_c_decisions = [
            e for e in events if e["branch_id"] == "route-c"
            and e["event_type"] in {"branch.selected", "branch.completed"}
        ]
        self.assertEqual([e["event_type"] for e in route_c_decisions],
                         ["branch.selected", "branch.completed"])
        self.assertTrue(all(e["actor_id"] == approver["participant_id"] for e in route_c_decisions))
        self.assertTrue(all(e["authority"] == "user_direct" for e in route_c_decisions))

        # The ledger preserves each agent as a distinct participant identity.
        for agent in (assistant, reviewer, implementer, validator):
            self.assertEqual(agent["participant_type"], "ai_agent")

        manager_events = [e for e in events if e["actor_id"] == manager["participant_id"]]
        self.assertEqual(manager_events, [])
        # Yet the manager is included during both the branch proposal and approval.
        self.assertIn(route_a_proposal["seq"], receipt["manager_present_event_seqs"])
        self.assertIn(route_c_decisions[0]["seq"], receipt["manager_present_event_seqs"])

    def test_portable_skill_log_is_generalised_and_keeps_synthetic_provenance(self):
        skill_path = ROOT / "examples" / "team-skill" / "portable-skill-log.json"
        skill_text = skill_path.read_text(encoding="utf-8")
        skill = json.loads(skill_text)

        self.assertEqual(skill["record_type"], "portable_team_skill")
        self.assertEqual(skill["maturity"], "candidate")
        self.assertEqual(
            skill["provenance"]["source_kind"],
            "synthetic_multi_agent_ledger_fixture",
        )
        self.assertEqual(
            skill["provenance"]["source_file"],
            "examples/multi-user-workflow/workflow.csv",
        )
        self.assertTrue(skill["provenance"]["source_steps"])
        self.assertFalse(skill["provenance"]["participant_names_included"])
        self.assertFalse(skill["provenance"]["participant_ids_included"])
        self.assertFalse(skill["provenance"]["account_project_or_chat_identifiers_included"])
        self.assertFalse(skill["provenance"]["raw_conversation_text_included"])

        # The portable form must not carry identities or scope identifiers from
        # the fixture it was distilled from.
        lowered = skill_text.casefold()
        for private_fixture_value in (
            "ari coordinator", "riley requester", "morgan manager",
            "sam approver", "example-org", "coordinator-01",
            "fixture-account", "multi-user-demo", "approval-workflow-demo",
            "agent:fixture:",
        ):
            self.assertNotIn(private_fixture_value.casefold(), lowered)

        self.assertIn("cross-boundary", skill["summary"])
        self.assertIn("passed_within_synthetic_fixture_only", skill["validation"]["status"])
        self.assertTrue(skill["limitations"])
        self.assertTrue(skill["reuse_guidance"])

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
