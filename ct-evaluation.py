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
        "schema_version": "1.1",
        "benchmark_id": benchmark["benchmark_id"],
        "benchmark_version": benchmark["version"],
        "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        "run_id": args.run_id or "ct-pilot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "created_at_utc": utc_now(),
        "protocol_deviations": [],
        "model": {
            "provider": args.provider or "", "name": args.model, "version": args.model_version,
            "settings": args.settings or "Record sampling settings or explicitly mark unknown.",
            "tool_access": args.tool_access or "Record available tools and whether used."
        },
        "skill": {"commit": "", "blob_sha": "", "notes": "Intended skill identity only; this metadata does not prove the skill was loaded."},
        "neutral_control": {"used": bool(args.include_neutral), "exact_instructions": ""},
        "execution": {
            "order_seed": args.seed, "case_order_by_condition": {},
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
                c: {"blind_response_id": "", "raw_response": "", "assessments": []}
                for c in CONDITIONS
            }
        })
    write_json(Path(args.output), scorecard)
    print(f"Created {args.output}")
    print(f"Benchmark: {benchmark['benchmark_id']} v{benchmark['version']}; {len(benchmark['cases'])} cases")
    print("Capture raw responses verbatim, then record each independent assessment separately.")
    print("Use scores 0-4 for applicable dimensions and null for non-applicable dimensions.")
    return 0


def _valid_score(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 4


def _normalized_assessments(response):
    """Read v1.1 independent ratings or adapt legacy v1.0 single ratings."""
    if not isinstance(response, dict):
        return []
    if "assessments" in response:
        assessments = response.get("assessments")
        return [a for a in assessments if isinstance(a, dict)] if isinstance(assessments, list) else []
    if "scores" in response:
        return [{"assessor_id": str(response.get("assessor") or "legacy-assessor"),
                 "scores": response.get("scores", {}),
                 "rationale_notes": response.get("rationale_notes", "")}]
    return []


def _validate_assessment(assessment, case_id, condition, index, applicable, errors, warnings):
    prefix = f"{case_id}/{condition}/assessment[{index}]"
    aid = assessment.get("assessor_id")
    if not isinstance(aid, str) or not aid.strip():
        errors.append(f"{prefix}: assessor_id must be a non-empty string")
    scores = assessment.get("scores", {})
    if not isinstance(scores, dict):
        errors.append(f"{prefix}: scores must be an object")
        scores = {}
    for dim in DIMENSIONS:
        value = scores.get(dim)
        if dim not in applicable and value is not None:
            errors.append(f"{prefix}/{dim}: must be null (not applicable)")
        elif dim in applicable and value is None:
            warnings.append(f"{prefix}/{dim}: score missing")
        elif value is not None and not _valid_score(value):
            errors.append(f"{prefix}/{dim}: score must be integer 0-4 or null")


def validate(scorecard, benchmark, benchmark_path):
    errors, warnings = [], []
    schema = str(scorecard.get("schema_version", "1.0"))
    if schema not in {"1.0", "1.1"}:
        errors.append(f"unsupported scorecard schema_version: {schema}")
    if scorecard.get("benchmark_id") != benchmark.get("benchmark_id"):
        errors.append("benchmark_id mismatch")
    if scorecard.get("benchmark_version") != benchmark.get("version"):
        errors.append("benchmark_version mismatch")
    if scorecard.get("benchmark_sha256") != hashlib.sha256(benchmark_path.read_bytes()).hexdigest():
        errors.append("benchmark file hash mismatch; scorecard was initialized from different benchmark content")

    model = scorecard.get("model", {})
    if not isinstance(model, dict) or not model.get("name") or not model.get("version"):
        warnings.append("model name/version incomplete")
    skill, settings = scorecard.get("skill", {}), scorecard.get("conditions", {})
    if not isinstance(skill, dict):
        skill = {}
    if not isinstance(settings, dict):
        settings = {}
    ct = settings.get("ct", {})
    if (ct.get("used", True) if isinstance(ct, dict) else True) and (not skill.get("commit") or not skill.get("blob_sha")):
        warnings.append("CT skill commit/blob pin missing")
    neutral = scorecard.get("neutral_control", {})
    if isinstance(neutral, dict) and neutral.get("used") and not neutral.get("exact_instructions"):
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

    for item in items:
        if not isinstance(item, dict) or item.get("case_id") not in expected:
            continue
        cid, source = item["case_id"], expected[item["case_id"]]
        if item.get("case_prompt_sha256") != hashlib.sha256(source["prompt"].encode("utf-8")).hexdigest():
            errors.append(f"{cid}: prompt hash mismatch")
        if item.get("applicable_dimensions") != source["applicable_dimensions"]:
            errors.append(f"{cid}: applicable dimensions differ from benchmark")
        responses = item.get("responses", {})
        if not isinstance(responses, dict):
            errors.append(f"{cid}: responses must be an object")
            continue
        for condition in CONDITIONS:
            setting = settings.get(condition, {})
            used = setting.get("used", condition != "neutral") if isinstance(setting, dict) else condition != "neutral"
            if not used:
                continue
            response = responses.get(condition)
            if not isinstance(response, dict):
                errors.append(f"{cid}/{condition}: response object missing")
                continue
            raw = response.get("raw_response", "")
            if not isinstance(raw, str) or not raw.strip():
                warnings.append(f"{cid}/{condition}: raw response missing")
            if raw and not response.get("blind_response_id"):
                warnings.append(f"{cid}/{condition}: blind_response_id missing")
            if "assessments" in response:
                if "scores" in response:
                    errors.append(f"{cid}/{condition}: cannot mix assessments[] with legacy response-level scores")
                assessments = response.get("assessments")
                if not isinstance(assessments, list):
                    errors.append(f"{cid}/{condition}: assessments must be a list")
                    continue
                if not assessments:
                    warnings.append(f"{cid}/{condition}: no assessor ratings")
                assessor_ids = []
                for index, assessment in enumerate(assessments):
                    if not isinstance(assessment, dict):
                        errors.append(f"{cid}/{condition}/assessment[{index}]: must be an object")
                        continue
                    aid = assessment.get("assessor_id")
                    if isinstance(aid, str) and aid.strip():
                        assessor_ids.append(aid.strip())
                    _validate_assessment(assessment, cid, condition, index, source["applicable_dimensions"], errors, warnings)
                if len(assessor_ids) != len(set(assessor_ids)):
                    errors.append(f"{cid}/{condition}: assessor_id values must be unique within the response")
            else:
                _validate_assessment({
                    "assessor_id": str(response.get("assessor") or "legacy-assessor"),
                    "scores": response.get("scores", {}),
                    "rationale_notes": response.get("rationale_notes", "")
                }, cid, condition, 0, source["applicable_dimensions"], errors, warnings)
    return errors, warnings


def validate_cmd(args):
    scorecard = load_json(Path(args.scorecard))
    benchmark_path = Path(args.benchmark) if args.benchmark else DEFAULT_BENCHMARK
    benchmark = load_json(benchmark_path)
    errors, warnings = validate(scorecard, benchmark, benchmark_path)
    for warning in warnings:
        print("WARNING:", warning)
    for error in errors:
        print("ERROR:", error)
    if errors:
        print(f"INVALID: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    if warnings:
        print(f"STRUCTURE VALID, INCOMPLETE: {len(warnings)} warning(s)")
        return 2 if args.require_complete else 0
    print("VALID: all used-condition responses and applicable assessment scores are complete")
    return 0


def mean(values):
    return round(statistics.mean(values), 3) if values else None


def _assessor_case_means(response, applicable):
    completed, by_dimension, assessments = [], {d: [] for d in DIMENSIONS}, _normalized_assessments(response)
    for assessment in assessments:
        aid = str(assessment.get("assessor_id") or "legacy-assessor")
        scores = assessment.get("scores", {})
        if not isinstance(scores, dict):
            continue
        values, complete = [], True
        for dim in applicable:
            value = scores.get(dim)
            if _valid_score(value):
                values.append(float(value))
                by_dimension[dim].append({"assessor_id": aid, "score": value})
            else:
                complete = False
        if complete and len(values) == len(applicable):
            completed.append({"assessor_id": aid, "mean_score": mean(values)})
    return completed, by_dimension, assessments


def make_report(scorecard, benchmark):
    benchmark_cases = {c["case_id"]: c for c in benchmark["cases"]}
    settings = scorecard.get("conditions", {})
    if not isinstance(settings, dict):
        settings = {}
    used = {c: (bool(settings.get(c, {}).get("used", c != "neutral"))
                if isinstance(settings.get(c, {}), dict) else c != "neutral")
            for c in CONDITIONS}
    dimension_values = {c: {d: [] for d in DIMENSIONS} for c in CONDITIONS}
    dimension_cases = {c: {d: [] for d in DIMENSIONS} for c in CONDITIONS}
    case_rows, deltas = [], {"ct_minus_baseline": [], "ct_minus_neutral": []}
    outcomes = {"ct_vs_baseline": {"win": 0, "tie": 0, "loss": 0},
                "ct_vs_neutral": {"win": 0, "tie": 0, "loss": 0}}

    for item in scorecard.get("cases", []):
        cid = item["case_id"]
        applicable = benchmark_cases[cid]["applicable_dimensions"]
        case_means, complete_counts, assessment_counts, disagreement = {}, {}, {}, {}
        for condition in CONDITIONS:
            response = item.get("responses", {}).get(condition, {})
            complete, by_dimension, assessments = _assessor_case_means(response, applicable)
            complete_counts[condition], assessment_counts[condition] = len(complete), len(assessments)
            case_means[condition] = mean([a["mean_score"] for a in complete])
            disagreement[condition] = {"assessment_count": len(assessments),
                "complete_assessment_count": len(complete), "dimensions": {}}
            for dim in applicable:
                ratings = by_dimension[dim]
                dimension_values[condition][dim].extend(float(r["score"]) for r in ratings)
                values = [r["score"] for r in ratings]
                n_assessors = len({r["assessor_id"] for r in ratings})
                detail = {"ratings": ratings, "n_ratings": len(values), "n_assessors": n_assessors,
                    "min": min(values) if values else None, "max": max(values) if values else None,
                    "range": max(values)-min(values) if len(values) >= 2 else None,
                    "disagreement": len(set(values)) > 1}
                disagreement[condition]["dimensions"][dim] = detail
                if values:
                    dimension_cases[condition][dim].append({"case_id": cid, "ratings": ratings,
                        "n_assessors": n_assessors, "min": min(values), "max": max(values),
                        "range": max(values)-min(values), "disagreement": len(set(values)) > 1})
        case_rows.append({"case_id": cid, "condition_mean_scores": case_means,
            "complete_assessment_counts": complete_counts, "assessment_counts": assessment_counts,
            "assessor_disagreement": disagreement})
        for comparator in ("baseline", "neutral"):
            if not used["ct"] or not used[comparator]:
                continue
            left, right = case_means["ct"], case_means[comparator]
            if left is None or right is None:
                continue
            delta = round(left-right, 3)
            deltas[f"ct_minus_{comparator}"].append(delta)
            outcomes[f"ct_vs_{comparator}"]["win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1

    condition_report, agreement_report = {}, {}
    for condition in CONDITIONS:
        if not used[condition]:
            condition_report[condition] = {"used": False}
            agreement_report[condition] = {"used": False}
            continue
        case_scores = [r["condition_mean_scores"][condition] for r in case_rows if r["condition_mean_scores"][condition] is not None]
        assessor_ids, count_all, count_complete = set(), 0, 0
        for item in scorecard.get("cases", []):
            response = item.get("responses", {}).get(condition, {})
            assessments = _normalized_assessments(response)
            count_all += len(assessments)
            complete, _, _ = _assessor_case_means(response, benchmark_cases[item["case_id"]]["applicable_dimensions"])
            count_complete += len(complete)
            assessor_ids.update(str(a["assessor_id"]) for a in assessments if a.get("assessor_id"))
        dim_report, agreement_dims = {}, {}
        for dim in DIMENSIONS:
            values, per_case = dimension_values[condition][dim], dimension_cases[condition][dim]
            multirater = [r for r in per_case if r["n_assessors"] >= 2]
            disagreed = [r for r in multirater if r["disagreement"]]
            distinct = {rating["assessor_id"] for row in case_rows
                for rating in row["assessor_disagreement"][condition]["dimensions"].get(dim, {}).get("ratings", [])}
            dim_report[dim] = {"mean_0_to_4": mean(values), "n_ratings": len(values),
                "min": min(values) if values else None, "max": max(values) if values else None,
                "n_distinct_assessors": len(distinct)}
            agreement_dims[dim] = {
                "n_case_dimensions_with_multiple_ratings": len(multirater),
                "n_case_dimensions_with_disagreement": len(disagreed),
                "mean_range_when_multiple_raters": mean([r["range"] for r in multirater]),
                "case_ranges": [{"case_id": r["case_id"], "n_assessors": r["n_assessors"],
                    "min": r["min"], "max": r["max"], "range": r["range"],
                    "disagreement": r["disagreement"]} for r in multirater]}
        condition_report[condition] = {"used": True, "mean_case_score_0_to_4": mean(case_scores),
            "n_complete_cases": len(case_scores), "assessment_count": count_all,
            "complete_assessment_count": count_complete, "n_distinct_assessors": len(assessor_ids),
            "dimensions": dim_report}
        agreement_report[condition] = {"used": True, "dimensions": agreement_dims}

    return {"report_schema_version": "1.1", "benchmark_id": scorecard.get("benchmark_id"),
        "benchmark_version": scorecard.get("benchmark_version"), "benchmark_sha256": scorecard.get("benchmark_sha256"),
        "scorecard_schema_version": str(scorecard.get("schema_version", "1.0")),
        "run_id": scorecard.get("run_id"), "generated_at_utc": utc_now(),
        "interpretation_notice": "Descriptive results for this model, setup, skill, rubric and task set only. Not proof of general CT efficacy or statistical significance. Assessor agreement is not proof of correctness.",
        "model": scorecard.get("model", {}), "skill": scorecard.get("skill", {}),
        "protocol_deviations": scorecard.get("protocol_deviations", []),
        "conditions": condition_report, "assessor_agreement": agreement_report,
        "paired_comparisons": {
            "ct_minus_baseline_mean_case_delta": mean(deltas["ct_minus_baseline"]),
            "ct_minus_baseline_n_paired_complete_cases": len(deltas["ct_minus_baseline"]),
            "ct_vs_baseline_outcomes": outcomes["ct_vs_baseline"],
            "ct_minus_neutral_mean_case_delta": mean(deltas["ct_minus_neutral"]),
            "ct_minus_neutral_n_paired_complete_cases": len(deltas["ct_minus_neutral"]),
            "ct_vs_neutral_outcomes": outcomes["ct_vs_neutral"]},
        "case_results": case_rows}

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

    rep = sub.add_parser("report", help="compute descriptive summaries, paired deltas, and assessor disagreement")
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
