#!/usr/bin/env python3
"""Focused, deterministic sanity tests for ct-evaluation.py and its benchmark."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ct-evaluation.py"
SPEC = importlib.util.spec_from_file_location("ct_evaluation_tool", SCRIPT)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
BENCHMARK_PATH = ROOT / "ct-evaluation" / "benchmark-v1.json"
BENCHMARK = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_has_ten_unique_cases(self):
        cases = BENCHMARK["cases"]
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({case["case_id"] for case in cases}), 10)

    def test_dimensions_and_anchors_are_well_formed(self):
        for case in BENCHMARK["cases"]:
            self.assertTrue(case["applicable_dimensions"])
            self.assertTrue(set(case["applicable_dimensions"]).issubset(TOOL.DIMENSIONS))
            self.assertTrue(set(case["applicable_dimensions"]).issubset(case["score_4_anchors"]))
            self.assertTrue(case["prompt"].strip())


class ScorecardTests(unittest.TestCase):
    def make_scorecard(self, include_neutral=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            args = type("Args", (), {
                "benchmark": str(BENCHMARK_PATH),
                "output": str(path),
                "model": "synthetic-test-model",
                "model_version": "test-0",
                "provider": "test",
                "settings": "deterministic synthetic data",
                "tool_access": "none",
                "run_id": "synthetic-test",
                "seed": 42,
                "include_neutral": include_neutral,
            })()
            TOOL.init_run(args)
            card = json.loads(path.read_text(encoding="utf-8"))
            card["skill"]["commit"] = "d1f23e2ad9dafd323940fc6b7a00f1700275d885"
            card["skill"]["blob_sha"] = "d7134969b124e39c04e343bed2ce2475f64b9a64"
            return card

    def fill_condition(self, card, condition, value):
        for case in card["cases"]:
            response = case["responses"][condition]
            response["blind_response_id"] = f'{case["case_id"]}-{condition}'
            response["raw_response"] = f"Synthetic fixture response for {condition}; not a real model result."
            response["assessor"] = "automated-fixture"
            response["scores"] = {
                dim: (value if dim in case["applicable_dimensions"] else None)
                for dim in TOOL.DIMENSIONS
            }

    def test_blank_scorecard_is_structurally_valid_but_incomplete(self):
        card = self.make_scorecard()
        errors, warnings = TOOL.validate(card, BENCHMARK, BENCHMARK_PATH)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_valid_paired_scores_produce_expected_descriptive_delta(self):
        card = self.make_scorecard()
        self.fill_condition(card, "baseline", 2)
        self.fill_condition(card, "ct", 3)
        errors, warnings = TOOL.validate(card, BENCHMARK, BENCHMARK_PATH)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        report = TOOL.make_report(card, BENCHMARK)
        self.assertEqual(report["conditions"]["baseline"]["mean_case_score_0_to_4"], 2)
        self.assertEqual(report["conditions"]["ct"]["mean_case_score_0_to_4"], 3)
        self.assertEqual(report["paired_comparisons"]["ct_minus_baseline_mean_case_delta"], 1)
        self.assertEqual(report["paired_comparisons"]["ct_minus_baseline_n_paired_complete_cases"], 10)

    def test_incomplete_case_is_excluded_from_paired_delta(self):
        card = self.make_scorecard()
        self.fill_condition(card, "baseline", 2)
        self.fill_condition(card, "ct", 3)
        first = card["cases"][0]
        first["responses"]["ct"]["scores"]["accuracy"] = None
        report = TOOL.make_report(card, BENCHMARK)
        self.assertEqual(report["paired_comparisons"]["ct_minus_baseline_n_paired_complete_cases"], 9)

    def test_invalid_score_is_rejected(self):
        card = self.make_scorecard()
        self.fill_condition(card, "baseline", 2)
        self.fill_condition(card, "ct", 3)
        card["cases"][0]["responses"]["ct"]["scores"]["accuracy"] = 7
        errors, _ = TOOL.validate(card, BENCHMARK, BENCHMARK_PATH)
        self.assertTrue(any("score must be integer 0-4" in err for err in errors))

    def test_benchmark_content_change_is_detected(self):
        card = self.make_scorecard()
        import copy
        changed = copy.deepcopy(BENCHMARK)
        changed["cases"][0]["prompt"] += " modified"
        errors, _ = TOOL.validate(card, changed, BENCHMARK_PATH)
        self.assertTrue(any("prompt hash mismatch" in err for err in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
