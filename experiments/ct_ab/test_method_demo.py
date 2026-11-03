"""Regression tests for the deterministic Q-Batch order/carryover demonstration."""
import json
import tempfile
import unittest
from pathlib import Path

from .method_demo import run_demo


class MethodDemoTests(unittest.TestCase):
    def test_order_effect_is_exposed_and_clean_runs_are_comparable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "batch"
            report = run_demo(output)
            self.assertEqual(report["status"], "PASS")
            analysis = report["analysis"]
            self.assertTrue(analysis["order_effect_detected"])
            self.assertTrue(analysis["isolated_conditions_comparable"])
            self.assertTrue(analysis["all_run_logs_validated"])
            self.assertEqual(analysis["runs"], 6)
            self.assertEqual(analysis["model_calls"], 0)
            self.assertEqual(analysis["sequential_ab_outcomes"], {
                "A": "clean_baseline", "B": "contaminated_by_A"
            })
            self.assertEqual(analysis["sequential_ba_outcomes"], {
                "B": "clean_baseline", "A": "contaminated_by_B"
            })
            self.assertEqual(analysis["isolated_outcomes"], {
                "A": "clean_baseline", "B": "clean_baseline"
            })
            # The manifest must identify the actual starting state. Sequential
            # B inherits A's state; isolated A and B share the same clean baseline.
            def base_state(scenario, label):
                path = output / "runs" / scenario / f"{scenario}-{label.lower()}" / "manifest.json"
                manifest = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["context_id"], "qbatch-method-order-carryover-v1")
                self.assertEqual(manifest["context"]["purpose"], "Test whether a Q-Batch evidence set can expose this specific sequential carryover confound and preserve enough evidence to inspect it.")
                return manifest["base_commit"]
            self.assertNotEqual(base_state("sequential_ab", "A"),
                                base_state("sequential_ab", "B"))
            self.assertNotEqual(base_state("sequential_ba", "B"),
                                base_state("sequential_ba", "A"))
            self.assertEqual(base_state("isolated", "A"), base_state("isolated", "B"))
            saved = json.loads((output / "method-report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["classification"],
                             "SYNTHETIC_METHODOLOGY_DEMONSTRATION_NOT_MODEL_EFFICACY")

    def test_existing_nonempty_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "batch"
            output.mkdir()
            (output / "keep.txt").write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                run_demo(output)
            self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
