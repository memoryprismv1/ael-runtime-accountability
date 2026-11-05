from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.ct_ab.scorecards import (
    DIMENSIONS,
    LEGACY_CASE_ID,
    ScorecardValidationError,
    build_report,
    main,
    validate_scorecard,
)


def dimension(score: int = 3, applicability: str = "applicable") -> dict:
    return {
        "applicability": applicability,
        "score": score if applicability == "applicable" else None,
        "rationale": "Assessment rationale supported by inspected evidence.",
        "evidence": ["source/app.py:route_handler"] if applicability == "applicable" else [],
    }


def assessment(assessor_id: str, score: int = 3, preference: str = "tie") -> dict:
    return {
        "assessor_id": assessor_id,
        "submitted_at_utc": "2026-11-05T10:00:00Z",
        "dimensions": {name: dimension(score) for name in DIMENSIONS},
        "overall_preference": preference,
        "confidence": 3,
        "notes": "Independent assessment.",
    }


def v2(label: str, assessors: list[dict], pair_id: str = "pair-1", case_id: str = "case-hash") -> dict:
    return {
        "schema_version": "2.0",
        "pair_id": pair_id,
        "case_id": case_id,
        "blind_label": label,
        "assessments": assessors,
    }


def v1(label: str = "A", assessor_id: str = "legacy-assessor", score: int = 4) -> dict:
    return {
        "schema_version": "1.0",
        "pair_id": "legacy-pair",
        "assessor_id": assessor_id,
        "blind_label": label,
        "submitted_at_utc": "2026-11-05T10:00:00Z",
        "dimensions": {
            name: {
                "score": score,
                "rationale": "Legacy rationale.",
                "evidence": ["source/app.py"],
            }
            for name in DIMENSIONS
        },
        "overall_preference": "A",
        "confidence": 4,
        "notes": "Legacy card remains readable.",
    }


class ScorecardTests(unittest.TestCase):
    def test_v2_accepts_multiple_independent_assessors(self):
        card = v2("A", [assessment("assessor-1", 2), assessment("assessor-2", 4)])
        self.assertEqual(validate_scorecard(card), [])

    def test_v2_rejects_duplicate_assessor_id_within_response(self):
        card = v2("A", [assessment("same"), assessment("same")])
        errors = validate_scorecard(card)
        self.assertTrue(any("duplicate assessor ID" in error for error in errors))

    def test_v2_rejects_scores_outside_integer_range(self):
        card = v2("A", [assessment("assessor-1")])
        card["assessments"][0]["dimensions"]["requirements_fidelity"]["score"] = 6
        self.assertTrue(any("integer from 1 to 5" in error for error in validate_scorecard(card)))

    def test_v2_rejects_boolean_score(self):
        card = v2("A", [assessment("assessor-1")])
        card["assessments"][0]["dimensions"]["requirements_fidelity"]["score"] = True
        self.assertTrue(any("integer from 1 to 5" in error for error in validate_scorecard(card)))

    def test_v2_checks_not_applicable_dimensions(self):
        card = v2("A", [assessment("assessor-1")])
        card["assessments"][0]["dimensions"]["interface_usability"] = dimension(3, "not_applicable")
        self.assertEqual(validate_scorecard(card), [])
        card["assessments"][0]["dimensions"]["interface_usability"]["score"] = 2
        self.assertTrue(any("must use null" in error for error in validate_scorecard(card)))

    def test_v2_requires_evidence_for_applicable_dimension(self):
        card = v2("A", [assessment("assessor-1")])
        card["assessments"][0]["dimensions"]["requirements_fidelity"]["evidence"] = []
        self.assertTrue(any("at least one item" in error for error in validate_scorecard(card)))

    def test_v2_validator_reports_unhashable_values_without_crashing(self):
        card = v2("A", [assessment("assessor-1")])
        card["blind_label"] = []
        card["assessments"][0]["dimensions"]["requirements_fidelity"]["applicability"] = []
        errors = validate_scorecard(card)
        self.assertTrue(any("blind_label" in error for error in errors))
        self.assertTrue(any("applicability" in error for error in errors))

    def test_v1_validator_reports_unhashable_blind_label_without_crashing(self):
        card = v1()
        card["blind_label"] = []
        errors = validate_scorecard(card)
        self.assertTrue(any("blind_label" in error for error in errors))

    def test_v2_rejects_missing_dimension_rating(self):
        card = v2("A", [assessment("assessor-1")])
        card["assessments"][0]["dimensions"].pop("functional_robustness")
        errors = validate_scorecard(card)
        self.assertTrue(any("missing keys" in error for error in errors))

    def test_legacy_pairs_without_case_ids_are_not_pooled_together(self):
        report = build_report([
            v1(label="A", assessor_id="assessor-1"),
            v1(label="B", assessor_id="assessor-1"),
            {**v1(label="A", assessor_id="assessor-2"), "pair_id": "another-legacy-pair"},
        ])
        legacy_case_ids = {row["case_id"] for row in report["ratings_by_blind_label_case_dimension"]}
        self.assertEqual(legacy_case_ids, {"legacy-unspecified:legacy-pair", "legacy-unspecified:another-legacy-pair"})

    def test_v1_single_assessor_card_remains_valid(self):
        self.assertEqual(validate_scorecard(v1()), [])

    def test_v1_is_normalized_into_legacy_case_without_inventing_case_id(self):
        report = build_report([v1()])
        self.assertEqual(report["input_counts"]["legacy_v1_files"], 1)
        self.assertEqual(report["ratings_by_blind_label_case_dimension"][0]["case_id"], f"{LEGACY_CASE_ID}:legacy-pair")

    def test_report_aggregates_descriptive_ranges_by_label_case_dimension(self):
        card_a = v2("A", [assessment("assessor-1", 2, "A"), assessment("assessor-2", 4, "A")])
        card_b = v2("B", [assessment("assessor-1", 3, "A"), assessment("assessor-2", 5, "A")])
        report = build_report([card_a, card_b])
        a_row = next(row for row in report["ratings_by_blind_label_case_dimension"]
                     if row["blind_label"] == "A" and row["dimension"] == "requirements_fidelity")
        self.assertEqual(a_row["assessor_count"], 2)
        self.assertEqual(a_row["minimum"], 2)
        self.assertEqual(a_row["maximum"], 4)
        self.assertEqual(a_row["score_range"], 2)
        self.assertTrue(a_row["disagreement_observed"])
        preference = report["pair_preferences"][0]
        self.assertEqual(preference["preference_counts"]["A"], 2)
        self.assertEqual(preference["conflict_count"], 0)

    def test_report_marks_dimension_agreement_when_assessors_match(self):
        card = v2("A", [assessment("assessor-1", 4), assessment("assessor-2", 4)])
        report = build_report([card])
        row = next(row for row in report["ratings_by_blind_label_case_dimension"]
                   if row["blind_label"] == "A" and row["dimension"] == "requirements_fidelity")
        self.assertEqual(row["distinct_score_count"], 1)
        self.assertEqual(row["score_range"], 0)
        self.assertFalse(row["disagreement_observed"])

    def test_assessor_count_is_unique_across_repeated_pairs(self):
        first_pair = v2("A", [assessment("assessor-1", 2)], pair_id="pair-1")
        second_pair = v2("A", [assessment("assessor-1", 3), assessment("assessor-2", 4)], pair_id="pair-2")
        report = build_report([first_pair, second_pair])
        row = next(row for row in report["ratings_by_blind_label_case_dimension"]
                   if row["blind_label"] == "A" and row["dimension"] == "requirements_fidelity")
        self.assertEqual(row["pair_count"], 2)
        self.assertEqual(row["assessment_count"], 3)
        self.assertEqual(row["assessor_count"], 2)

    def test_report_excludes_not_applicable_dimensions_from_score_stats(self):
        card = v2("A", [assessment("assessor-1", 4)])
        card["assessments"][0]["dimensions"]["process_discipline"] = dimension(3, "not_applicable")
        report = build_report([card])
        row = next(row for row in report["ratings_by_blind_label_case_dimension"]
                   if row["dimension"] == "process_discipline")
        self.assertEqual(row["not_applicable_count"], 1)
        self.assertEqual(row["applicable_assessment_count"], 0)
        self.assertIsNone(row["mean"])

    def test_pair_preference_requires_both_blind_submissions(self):
        card_a = v2("A", [assessment("assessor-1", 3, "A")])
        report = build_report([card_a])
        preference = report["pair_preferences"][0]
        self.assertEqual(preference["assessor_count"], 0)
        self.assertEqual(preference["incomplete_assessor_count"], 1)
        self.assertEqual(preference["incomplete_assessments"][0]["missing_labels"], ["B"])
        self.assertEqual(preference["preference_counts"]["A"], 0)

    def test_pair_preference_conflicts_are_reported_not_averaged(self):
        card_a = v2("A", [assessment("assessor-1", 3, "A")])
        card_b = v2("B", [assessment("assessor-1", 3, "B")])
        report = build_report([card_a, card_b])
        preference = report["pair_preferences"][0]
        self.assertEqual(preference["assessor_count"], 0)
        self.assertEqual(preference["conflict_count"], 1)
        self.assertEqual(preference["conflicting_assessments"][0]["observed_preferences"], {"A": "A", "B": "B"})

    def test_duplicate_assessor_across_files_for_same_response_is_rejected(self):
        card_1 = v2("A", [assessment("assessor-1", 2)])
        card_2 = v2("A", [assessment("assessor-1", 4)])
        with self.assertRaises(ScorecardValidationError):
            build_report([card_1, card_2])

    def test_cli_validates_legacy_and_v2_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "scorecard-A-legacy.json"
            current = root / "scorecard-B-current.json"
            legacy.write_text(json.dumps(v1()), encoding="utf-8")
            current.write_text(json.dumps(v2("B", [assessment("assessor-2")])), encoding="utf-8")
            self.assertEqual(main(["validate", str(legacy), str(current)]), 0)
            output = root / "summary.json"
            self.assertEqual(main(["report", str(legacy), str(current), "--out", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["input_counts"]["scorecard_files"], 2)

    def test_cli_validate_rejects_duplicate_assessor_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "scorecard-A-first.json"
            second = root / "scorecard-A-second.json"
            first.write_text(json.dumps(v2("A", [assessment("same-assessor", 2)])), encoding="utf-8")
            second.write_text(json.dumps(v2("A", [assessment("same-assessor", 4)])), encoding="utf-8")
            self.assertEqual(main(["validate", str(first), str(second)]), 1)

    def test_cli_directory_search_excludes_blank_template_and_prior_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scorecard-template.json").write_text("{}", encoding="utf-8")
            (root / "scorecard-report.json").write_text("{}", encoding="utf-8")
            (root / "scorecard-v1.schema.json").write_text("{}", encoding="utf-8")
            (root / "scorecard-A.json").write_text(json.dumps(v2("A", [assessment("assessor-1")])), encoding="utf-8")
            output = root / "report.json"
            self.assertEqual(main(["report", str(root), "--out", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["input_counts"]["scorecard_files"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
