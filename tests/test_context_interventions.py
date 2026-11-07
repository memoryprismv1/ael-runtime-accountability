import tempfile
import unittest
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runtime


class ContextInterventionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.con = runtime.connect(self.root / "context-intervention.sqlite3")
        self.account, self.project, self.chat = "acct-context", "project-context", "chat-context"
        self.manager = runtime.register_participant(
            self.con, account=self.account, issuer="context-org", external_id="manager-1",
            identity_source="organisation", participant_type="human", display_name="Morgan",
        )["participant_id"]
        runtime.join_participant(
            self.con, account=self.account, project=self.project, chat=self.chat,
            participant_id=self.manager, role="manager", actor_id=runtime.SYSTEM_ACTOR_ID,
        )

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def transcript(self):
        return [
            (event["event_type"], event["content"])
            for event in runtime.scope_events(self.con, self.account, self.project, self.chat)
            if event["event_type"] in {"user_message", "assistant_message"}
        ]

    def model_input(self):
        payload = runtime.hydrate_payload(
            self.con, account=self.account, project=self.project, chat=self.chat
        )
        return runtime.build_model_input(payload, "What is the current approval route?", max_tokens=4000)

    def test_external_context_changes_model_input_without_changing_message_transcript(self):
        runtime.append_event(
            self.con, account=self.account, project=self.project, chat=self.chat,
            event_type="user_message", provenance="user", content="Please review this request.",
        )
        transcript_before = self.transcript()
        input_before, audit_before = self.model_input()

        first = runtime.record_context_intervention(
            self.con, account=self.account, project=self.project, chat=self.chat,
            resource_id="shared-approval-guide", resource_type="project_instruction",
            version="v1", content="All approvals require a human reviewer.",
            actor_id=self.manager, authority="user_direct", source_ref="project-settings:approval-guide:v1",
        )
        input_after, audit_after = self.model_input()
        self.assertEqual(self.transcript(), transcript_before)
        self.assertNotEqual(audit_before["context_sha256"], audit_after["context_sha256"])
        self.assertIn("All approvals require a human reviewer.", input_after["working_context"])
        self.assertNotIn("All approvals require a human reviewer.", input_before["working_context"])
        self.assertEqual(audit_after["context_interventions"][0]["actor_id"], self.manager)
        import json
        first_metadata = json.loads(first["metadata_json"])
        self.assertEqual(audit_after["context_interventions"][0]["content_sha256"], first_metadata["content_sha256"])

        second = runtime.record_context_intervention(
            self.con, account=self.account, project=self.project, chat=self.chat,
            resource_id="shared-approval-guide", resource_type="project_instruction",
            version="v2", content="Approvals require the named approver's explicit selection.",
            actor_id=self.manager, authority="user_direct", source_ref="project-settings:approval-guide:v2",
            expected_previous_sha256=first_metadata["content_sha256"],
        )
        input_latest, audit_latest = self.model_input()
        self.assertIn("Approvals require the named approver's explicit selection.", input_latest["working_context"])
        self.assertNotIn("All approvals require a human reviewer.", input_latest["working_context"])
        self.assertEqual(len(audit_latest["context_interventions"]), 1)
        self.assertEqual(audit_latest["context_interventions"][0]["version"], "v2")
        self.assertEqual(self.transcript(), transcript_before)
        all_versions = [e for e in runtime.scope_events(self.con, self.account, self.project, self.chat)
                        if e["event_type"] == "context.intervened"]
        self.assertEqual(len(all_versions), 2)
        projection = runtime.hydrate_payload(self.con, account=self.account, project=self.project, chat=self.chat)
        self.assertEqual(len([e for e in projection["excluded_from_active_context"]
                              if e["event_type"] == "context.intervened"]), 1)
        self.assertEqual(second["actor_id"], self.manager)

    def test_context_intervention_rejects_unjoined_actor_and_stale_base_hash(self):
        outsider = runtime.register_participant(
            self.con, account=self.account, issuer="context-org", external_id="outsider-2",
            identity_source="organisation", participant_type="human", display_name="Alex",
        )["participant_id"]
        with self.assertRaisesRegex(ValueError, "not an active participant"):
            runtime.record_context_intervention(
                self.con, account=self.account, project=self.project, chat=self.chat,
                resource_id="shared-guide", resource_type="context_file", version="v1",
                content="A change from outside the participant chain.", actor_id=outsider,
                authority="user_direct",
            )
        first = runtime.record_context_intervention(
            self.con, account=self.account, project=self.project, chat=self.chat,
            resource_id="shared-guide", resource_type="context_file", version="v1",
            content="Initial content.", actor_id=self.manager, authority="user_direct",
        )
        with self.assertRaisesRegex(ValueError, "changed since the expected previous hash"):
            runtime.record_context_intervention(
                self.con, account=self.account, project=self.project, chat=self.chat,
                resource_id="shared-guide", resource_type="context_file", version="v2",
                content="Concurrent update.", actor_id=self.manager, authority="user_direct",
                expected_previous_sha256="stale-hash",
            )
        self.assertEqual(len([e for e in runtime.scope_events(self.con, self.account, self.project, self.chat)
                              if e["event_type"] == "context.intervened"]), 1)


if __name__ == "__main__":
    unittest.main()
