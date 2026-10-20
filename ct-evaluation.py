#!/usr/bin/env python3
"""Manual scorecard and descriptive-report tool for the CT pilot.

No model is called and no response is automatically judged. Raw responses are
captured by the operator; scores must be entered using the pinned rubric.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_BENCHMARK = ROOT / "ct-evaluation" / "benchmark-v1.json"
CONDITIONS = ("baseline", "ct", "neutral")
DIMENSIONS = ("accuracy", "evidence", "contradictions_alternatives", "calibration", "scope_discipline")


def load_json(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_run(args):
    benchmark_path = Path(args.benchmark) if args.benchmark else DEFAULT_BENCHMARK
    benchmark = load_json(benchmark_path)
    scorecard = {
        "schema_version": "1.0",
        "benchmark_id": benchmark["benchmark_id"],
        "benchmark_version": benchmark["version"],
        "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        "run_id": args.run_id or "ct-pilot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "created_at_utc": utc_now(),
        "protocol_deviations": [],
        "model": {
            "provider": args.provider or "",
            "name": args.model,
            "version": args.model_version,
            "settings": args.settings or "Record sampling settings or explicitly mark unknown.",
            "tool_access": args.tool_access or "Record available tools and whether used."
        },
        "skill": {
            "commit": "",
            "blob_sha": "",
            "notes": "These identify the skill artifact intended for the CT condition; this metadata does not itself prove the skill was loaded."
        },
        "neutral_control": {"used": bool(args.include_neutral), "exact_instructions": ""},
        "execution": {
            "order_seed": args.seed,
            "case_order_by_condition": {},
            "isolation_and_run_notes": "Record fresh-session method, run order, failures, and deviations."
        },
        "conditions": {
            c: {"used": (c != "neutral" or args.include_neutral), "instruction_or_skill_setup": ""}
            for c in CONDITIONS
        },
        "cases": []
    }
    for case in benchmark["cases"]:
        scorecard["cases"].append({
            "case_id": case["case_id"],
            "case_prompt_sha256": hashlib.sha256(case["prompt"].encode("utf-8")).hexdigest(),
            "applicable_dimensions": case["applicable_dimensions"],
            "responses": {
                c: {
                    "blind_response_id": "",
                    "raw_response": "",
                    "assessor": "",
                    "scores": {d: None for d in DIMENSIONS},
                    "rationale_notes": ""
                } for c in CONDITIONS
            }
        })
    write_json(Path(args.output), scorecard)
    print(f"Created {args.output}")
    print(f"Benchmark: {benchmark['benchmark_id']} v{benchmark['version']}; {len(benchmark['cases'])} cases")
    print("Fill run metadata, capture responses verbatim, score applicable dimensions 0-4, leave non-applicable dimensions null.")
    return 0


def validate(scorecard, benchmark, benchmark_path):
    errors, warnings = [], []
    if scorecard.get("benchmark_id") != benchmark.get("benchmark_id"):
        errors.append("benchmark_id mismatch")
    if scorecard.get("benchmark_version") != benchmark.get("version"):
        errors.append("benchmark_version mismatch")
    expected_hash = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
    if scorecard.get("benchmark_sha256") != expected_hash:
        errors.append("benchmark file hash mismatch; scorecard was initialized from different benchmark content")
    model = scorecard.get("model", {})
    if not model.get("name") or not model.get("version"):
        warnings.append("model name/version incomplete")
    skill = scorecard.get("skill", {})
    if scorecard.get("conditions", {}).get("ct", {}).get("used", True) and (not skill.get("commit") or not skill.get("blob_sha")):
        warnings.append("CT skill commit/blob pin missing")
    if scorecard.get("neutral_control", {}).get("used") and not scorecard.get("neutral_control", {}).get("exact_instructions"):
        warnings.append("neutral condition enabled but exact instructions missing")

    expected = {c["case_id"]: c for c in benchmark.get("cases", [])}
    items = scorecard.get("cases", [])
    if not isinstance(items, list):
        return ["cases must be a list"], warnings
    ids = [x.get("case_id") for x in items if isinstance(x, dict)]
    if len(ids) != len(set(ids)):
        errors.append("duplicate case_id")
    if set(ids) != set(expected):
        errors.append("case IDs do not exactly match benchmark")
    used_conditions = scorecard.get("conditions", {})
    for item in items:
        if not isinstance(item, dict) or item.get("case_id") not in expected:
            continue
        source = expected[item["case_id"]]
        if item.get("case_prompt_sha256") != hashlib.sha256(source["prompt"].encode("utf-8")).hexdigest():
            errors.append(f'{item["case_id"]}: prompt hash mismatch')
        if item.get("applicable_dimensions") != source["applicable_dimensions"]:
            errors.append(f'{item["case_id"]}: applicable dimensions differ from benchmark')
        for condition in CONDITIONS:
            if not used_conditions.get(condition, {}).get("used", condition != "neutral"):
                continue
            response = item.get("responses", {}).get(condition)
            if not isinstance(response, dict):
                errors.append(f'{item["case_id"]}/{condition}: response object missing')
                continue
            if not str(response.get("raw_response", "")).strip():
                warnings.append(f'{item["case_id"]}/{condition}: raw response missing')
            if response.get("raw_response") and not response.get("blind_response_id"):
                warnings.append(f'{item["case_id"]}/{condition}: blind_response_id missing')
            scores = response.get("scores", {})
            for dim in DIMENSIONS:
                value = scores.get(dim)
                applicable = dim in source["applicable_dimensions"]
                if not applicable and value is not None:
                    errors.append(f'{item["case_id"]}/{condition}/{dim}: must be null (not applicable)')
                elif applicable and value is None:
                    warnings.append(f'{item["case_id"]}/{condition}/{dim}: score missing')
                elif value is not None and (
                    isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 4
                ):
                    errors.append(f'{item["case_id"]}/{condition}/{dim}: score must be integer 0-4 or null')
    return errors, warnings


def validate_cmd(args):
    scorecard = load_json(Path(args.scorecard))
    benchmark_path = Path(args.benchmark) if args.benchmark else DEFAULT_BENCHMARK
    benchmark = load_json(benchmark_path)
    errors, warnings = validate(scorecard, benchmark, benchmark_path)
    for message in warnings:
        print("WARNING:", message)
    for message in errors:
        print("ERROR:", message)
    if errors:
        print(f"INVALID: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    if warnings:
        print(f"STRUCTURE VALID, INCOMPLETE: {len(warnings)} warning(s)")
        return 2 if args.require_complete else 0
    print("VALID: all used-condition responses and applicable scores are complete")
    return 0


def mean(values):
    return round(statistics.mean(values), 3) if values else None


def make_report(scorecard, benchmark):
    bench_cases = {c["case_id"]: c for c in benchmark["cases"]}
    used = {c: bool(scorecard.get("conditions", {}).get(c, {}).get("used", c != "neutral")) for c in CONDITIONS}
    dim_values = {c: {d: [] for d in DIMENSIONS} for c in CONDITIONS}
    case_rows = []
    deltas = {"ct_minus_baseline": [], "ct_minus_neutral": []}
    outcomes = {
        "ct_vs_baseline": {"win": 0, "tie": 0, "loss": 0},
        "ct_vs_neutral": {"win": 0, "tie": 0, "loss": 0}
    }
    for item in scorecard.get("cases", []):
        cid = item["case_id"]
        applicable = bench_cases[cid]["applicable_dimensions"]
        case_means = {}
        for condition in CONDITIONS:
            raw_scores = item["responses"].get(condition, {}).get("scores", {})
            vals = []
            for dim in applicable:
                value = raw_scores.get(dim)
                if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 4:
                    vals.append(float(value))
                    dim_values[condition][dim].append(float(value))
            # Use a case in paired comparison only if every applicable dimension is scored.
            case_means[condition] = mean(vals) if len(vals) == len(applicable) else None
        case_rows.append({"case_id": cid, "condition_mean_scores": case_means})
        for condition in ("baseline", "neutral"):
            if not used["ct"] or not used[condition]:
                continue
            left, right = case_means["ct"], case_means[condition]
            if left is None or right is None:
                continue
            delta = round(left - right, 3)
            key = f"ct_minus_{condition}"
            deltas[key].append(delta)
            pair_key = f"ct_vs_{condition}"
            outcomes[pair_key]["win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1

    condition_report = {}
    for condition in CONDITIONS:
        if not used[condition]:
            condition_report[condition] = {"used": False}
            continue
        means_for_cases = [
            row["condition_mean_scores"][condition] for row in case_rows
            if row["condition_mean_scores"][condition] is not None
        ]
        condition_report[condition] = {
            "used": True,
            "mean_case_score_0_to_4": mean(means_for_cases),
            "n_complete_cases": len(means_for_cases),
            "dimensions": {
                dim: {"mean_0_to_4": mean(dim_values[condition][dim]), "n_scored": len(dim_values[condition][dim])}
                for dim in DIMENSIONS
            }
        }
    return {
        "report_schema_version": "1.0",
        "benchmark_id": scorecard.get("benchmark_id"),
        "benchmark_version": scorecard.get("benchmark_version"),
        "benchmark_sha256": scorecard.get("benchmark_sha256"),
        "run_id": scorecard.get("run_id"),
        "generated_at_utc": utc_now(),
        "interpretation_notice": "Descriptive results for this model, rubric, skill and task set only. Not proof of general CT efficacy or statistical significance.",
        "model": scorecard.get("model", {}),
        "skill": scorecard.get("skill", {}),
        "protocol_deviations": scorecard.get("protocol_deviations", []),
        "conditions": condition_report,
        "paired_comparisons": {
            "ct_minus_baseline_mean_case_delta": mean(deltas["ct_minus_baseline"]),
            "ct_minus_baseline_n_paired_complete_cases": len(deltas["ct_minus_baseline"]),
            "ct_vs_baseline_outcomes": outcomes["ct_vs_baseline"],
            "ct_minus_neutral_mean_case_delta": mean(deltas["ct_minus_neutral"]),
            "ct_minus_neutral_n_paired_complete_cases": len(deltas["ct_minus_neutral"]),
            "ct_vs_neutral_outcomes": outcomes["ct_vs_neutral"]
        },
        "case_results": case_rows
    }


def report_cmd(args):
    scorecard = load_json(Path(args.scorecard))
    benchmark_path = Path(args.benchmark) if args.benchmark else DEFAULT_BENCHMARK
    benchmark = load_json(benchmark_path)
    errors, warnings = validate(scorecard, benchmark, benchmark_path)
    if errors:
        for message in errors:
            print("ERROR:", message, file=sys.stderr)
        return 1
    report = make_report(scorecard, benchmark)
    if args.out:
        write_json(Path(args.out), report)
        print(f"Wrote {args.out}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if warnings:
        print(f"NOTE: incomplete data: {len(warnings)} warning(s)", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a blank scorecard")
    init.add_argument("--output", required=True)
    init.add_argument("--model", required=True)
    init.add_argument("--model-version", required=True)
    init.add_argument("--provider", default="")
    init.add_argument("--settings", default="")
    init.add_argument("--tool-access", default="")
    init.add_argument("--run-id", default="")
    init.add_argument("--seed", type=int, default=20261021)
    init.add_argument("--include-neutral", action="store_true")
    init.add_argument("--benchmark", default="")
    init.set_defaults(func=init_run)

    val = sub.add_parser("validate", help="check scorecard consistency/completeness")
    val.add_argument("scorecard")
    val.add_argument("--benchmark", default="")
    val.add_argument("--require-complete", action="store_true")
    val.set_defaults(func=validate_cmd)

    rep = sub.add_parser("report", help="compute descriptive summary and paired deltas")
    rep.add_argument("scorecard")
    rep.add_argument("--out", default="")
    rep.add_argument("--benchmark", default="")
    rep.set_defaults(func=report_cmd)

    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
