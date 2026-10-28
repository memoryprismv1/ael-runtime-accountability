"""Deterministic demonstration of order/carryover confounding and clean-baseline batching.

This is a methodology fixture, not an AI/model efficacy experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .logger import LOGGER_VERSION, SCHEMA_VERSION, RunLogger, sha256_bytes, utc_now
from .validate_log import validate_run

TASK = (
    "Demonstrate a sequential order/carryover confound using a deterministic "
    "stateful fixture; compare with independent clean-baseline runs."
)
TASK_SHA = sha256_bytes(TASK.encode("utf-8"))
CONFIG_SHA = sha256_bytes(b"qbatch-order-carryover-fixture-v1")
MODEL = {"provider": "synthetic-fixture", "model_id": "deterministic-state-machine-v1"}
ENVIRONMENT = {"execution": "local-python", "network": False, "model_inference": False}
LIMITS = {"model_calls": 0, "external_commands": 0, "max_runs": 8}


def _state_hash(state: dict[str, Any]) -> str:
    return sha256_bytes(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _run_condition(root: Path, scenario: str, label: str, order_index: int,
                   state: dict[str, Any], isolated: bool) -> dict[str, Any]:
    run_id = f"{scenario.lower()}-{label.lower()}"
    workspace = root / "workspaces" / run_id
    run_dir = root / "runs" / scenario / run_id
    workspace.mkdir(parents=True, exist_ok=False)
    before = dict(state)
    manifest = {
        "run_id": run_id,
        "condition_label": label,
        "task_brief_sha256": TASK_SHA,
        "condition_config_sha256": CONFIG_SHA,
        "logger_version": LOGGER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "started_at_utc": utc_now(),
        "model": MODEL,
        "environment": ENVIRONMENT,
        "resource_limits": LIMITS,
        "base_commit": "fixture-baseline-sha256:" + _state_hash({"prior_condition": None}),
    }
    logger = RunLogger(run_dir, workspace, manifest)
    try:
        initial = {"scenario": scenario, "condition": label, "execution_order": order_index,
                   "isolated_clean_baseline": isolated, "state_before": before,
                   "state_before_sha256": _state_hash(before)}
        initial_ref = logger.capture_artifact(f"{label.lower()}-state-before.json",
                                               json.dumps(initial, indent=2, sort_keys=True),
                                               "application/json")
        logger.emit("preflight_check", "runner", "preflight", "succeeded",
                    {"check": "declared_initial_state", **initial}, [initial_ref])

        # Intentional flaw: the first condition claims the clean-start benefit;
        # every later condition observes which condition ran immediately before it.
        prior = state.get("prior_condition")
        outcome = "clean_baseline" if prior is None else f"contaminated_by_{prior}"
        state["prior_condition"] = label
        final = {"scenario": scenario, "condition": label, "execution_order": order_index,
                 "outcome": outcome, "state_before": before, "state_after": dict(state),
                 "state_before_sha256": _state_hash(before), "state_after_sha256": _state_hash(state),
                 "isolated_clean_baseline": isolated}
        result_ref = logger.capture_artifact(f"{label.lower()}-fixture-result.json",
                                              json.dumps(final, indent=2, sort_keys=True),
                                              "application/json")
        logger.emit("requirement_check", "reviewer", "verification",
                    "succeeded" if outcome == "clean_baseline" else "failed",
                    {"requirement_id": "fixture-clean-baseline",
                     "result": "pass" if outcome == "clean_baseline" else "fail",
                     "outcome": outcome, "execution_order": order_index,
                     "state_before_sha256": final["state_before_sha256"],
                     "state_after_sha256": final["state_after_sha256"],
                     "isolated_clean_baseline": isolated}, [result_ref])
        logger.finish("succeeded", "Fixture executed successfully; outcome may intentionally expose carryover.")
    finally:
        logger.close()
    validation = validate_run(run_dir)
    return {"scenario": scenario, "condition": label, "execution_order": order_index,
            "outcome": outcome, "state_before_sha256": final["state_before_sha256"],
            "state_after_sha256": final["state_after_sha256"],
            "isolated_clean_baseline": isolated, "run_dir": str(run_dir),
            "validation": validation["status"], "events": validation["events"],
            "evidence_refs_verified": validation["evidence_refs_verified"]}


def run_demo(output: str | Path) -> dict[str, Any]:
    root = Path(output).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"output must be new or empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "runs").mkdir()
    (root / "workspaces").mkdir()

    scenarios: dict[str, list[dict[str, Any]]] = {}
    # Two ordinary sequential comparisons, reversing order to expose order effects.
    for scenario, order in (("sequential_ab", ("A", "B")), ("sequential_ba", ("B", "A"))):
        shared_state: dict[str, Any] = {"prior_condition": None}
        rows = []
        for index, label in enumerate(order, start=1):
            rows.append(_run_condition(root, scenario, label, index, shared_state, False))
        scenarios[scenario] = rows

    # Each condition gets a newly initialized state; execution order cannot carry over.
    rows = []
    for index, label in enumerate(("A", "B"), start=1):
        rows.append(_run_condition(root, "isolated", label, index, {"prior_condition": None}, True))
    scenarios["isolated"] = rows

    ab = {row["condition"]: row["outcome"] for row in scenarios["sequential_ab"]}
    ba = {row["condition"]: row["outcome"] for row in scenarios["sequential_ba"]}
    isolated = {row["condition"]: row["outcome"] for row in scenarios["isolated"]}
    order_effect_detected = ab != ba
    isolated_comparable = isolated == {"A": "clean_baseline", "B": "clean_baseline"}
    all_logs_valid = all(row["validation"] == "succeeded" for rows in scenarios.values() for row in rows)
    report = {
        "status": "PASS" if order_effect_detected and isolated_comparable and all_logs_valid else "FAIL",
        "classification": "SYNTHETIC_METHODOLOGY_DEMONSTRATION_NOT_MODEL_EFFICACY",
        "purpose": "Show that sequential shared-state comparisons can be order-dependent, while independently reset runs expose the confound.",
        "fixture_definition": "The first condition sees clean state; each later condition sees prior_condition left by the immediately preceding run.",
        "results": scenarios,
        "analysis": {
            "sequential_ab_outcomes": ab,
            "sequential_ba_outcomes": ba,
            "isolated_outcomes": isolated,
            "order_effect_detected": order_effect_detected,
            "isolated_conditions_comparable": isolated_comparable,
            "all_run_logs_validated": all_logs_valid,
            "runs": sum(len(rows) for rows in scenarios.values()),
            "model_calls": 0,
            "external_services": 0,
        },
        "limitations": [
            "The state carryover is deliberately constructed; this demonstrates one known failure mode, not its prevalence in real experiments.",
            "This tests evidence capture and comparison methodology, not model quality, skill efficacy, or universal superiority over A/B testing.",
            "A real system must identify and record its relevant state boundaries; Q-Batch cannot eliminate hidden carryover automatically."
        ]
    }
    (root / "method-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if report["status"] != "PASS":
        raise RuntimeError("method demonstration failed its expected assertions; inspect method-report.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New or empty directory for immutable demonstration evidence")
    args = parser.parse_args()
    report = run_demo(args.output)
    print(json.dumps({"status": report["status"], "classification": report["classification"],
                      "analysis": report["analysis"], "report": str(Path(args.output).resolve() / "method-report.json")},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
