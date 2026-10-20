import unittest
from compare_environments import pair, parse_test_results


class ComparisonHarnessTests(unittest.TestCase):
    def test_parser_extracts_test_statuses(self):
        output = (
            "test_alpha (test_mod.Sample.test_alpha) ... ok\n"
            "test_beta (test_mod.Sample.test_beta) ... FAIL\n"
        )
        parsed = parse_test_results(output)
        self.assertEqual(parsed, {
            "test_mod.Sample.test_alpha": "ok",
            "test_mod.Sample.test_beta": "FAIL",
        })

    def test_comparison_detects_shared_regression_and_tree_specific_tests(self):
        result = pair("baseline", "ct", {
            "baseline": {"Class.test_same": "ok", "Class.test_old": "ok"},
            "ct": {"Class.test_same": "FAIL", "Class.test_new": "ok"},
        })
        self.assertFalse(result["shared_tests_match"])
        self.assertEqual(result["baseline_pass_to_experiment_failure"][0]["test"], "Class.test_same")
        self.assertEqual(result["first_only_tests"], ["Class.test_old"])
        self.assertEqual(result["second_only_tests"], ["Class.test_new"])


if __name__ == "__main__":
    unittest.main()
