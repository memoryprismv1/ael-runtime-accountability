import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from qbatch_basic_review import review


class BasicReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = self.root / "unit-test-run.log"
        self.record = self.root / "unit-test-evidence.json"
        self.log.write_text("Ran 2 tests in 0.01s\n\nOK\n", encoding="utf-8")
        digest = hashlib.sha256(self.log.read_bytes()).hexdigest()
        self.record.write_text(json.dumps({
            "schema_version": "qbatch-ael-runtime-evidence/0.1",
            "batch_id": "test-batch",
            "status": "passed",
            "execution": {"exit_code": 0, "tests_reported": 2, "log_sha256": digest,
                          "real_model_inference_performed": False},
            "outputs": [{"path": self.log.name, "sha256": digest}]
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_record_and_log_pass_basic_checks(self):
        findings = review(self.record, self.log)
        self.assertFalse(any(severity == "BLOCKER" for severity, _, _ in findings))
        self.assertTrue(any(name == "Raw log hash matches" for _, name, _ in findings))

    def test_tampered_log_is_blocked(self):
        self.log.write_text("tampered\n", encoding="utf-8")
        findings = review(self.record, self.log)
        self.assertTrue(any(severity == "BLOCKER" and name == "Log hash mismatch"
                            for severity, name, _ in findings))

    def test_nonzero_exit_is_blocked(self):
        data = json.loads(self.record.read_text(encoding="utf-8"))
        data["execution"]["exit_code"] = 1
        self.record.write_text(json.dumps(data), encoding="utf-8")
        findings = review(self.record, self.log)
        self.assertTrue(any(severity == "BLOCKER" and name == "Run did not pass"
                            for severity, name, _ in findings))

    def test_missing_log_is_blocked(self):
        findings = review(self.record, self.root / "missing.log")
        self.assertTrue(any(severity == "BLOCKER" and name == "Raw log missing"
                            for severity, name, _ in findings))


if __name__ == "__main__":
    unittest.main()
