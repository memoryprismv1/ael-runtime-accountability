"""Validate and summarize independent CT assessor scorecards.

Version 1.0 single-assessor cards remain readable. Version 2.0 cards collect
multiple independent assessments for one blind response without pooling them.
Only the blind label (A/B) is reported; treatment mapping stays controller-private.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DIMENSIONS = (
    "requirements_fidelity",
    "functional_robustness",
    "interface_usability",
    "maintainability_simplicity",
    "testing_documentation",
    "process_discipline",
)
PREFERENCES = ("A", "B", "tie", "unable_to_judge")
LEGACY_CASE_ID = "legacy-unspecified"


class ScorecardValidationError(ValueError):
    """Raised when a scorecard cannot safely enter a report."""


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _timestamp_error(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{path}: expected an ISO 8601 date-time string")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{path}: invalid ISO 8601 date-time")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{path}: timestamp must include a timezone")


def _keys_error(value: dict[str, Any], required: set[str], path: str, errors: list[str]) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing:
        errors.append(f"{path}: missing keys {missing}")
    if extra:
        errors.append(f"{path}: unexpected keys {extra}")


def _validate_dimensions(value: Any, path: str, version: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected an object")
        return
    _keys_error(value, set(DIMENSIONS), path, errors)
    for name in DIMENSIONS:
        if name not in value:
            continue
        item = value[name]
        item_path = f"{path}.{name}"
        if not isinstance(item, dict):
            errors.append(f"{item_path}: expected an object")
            continue
        if version == "1.0":
            _keys_error(item, {"score", "rationale", "evidence"}, item_path, errors)
            applicable = True
        else:
            _keys_error(item, {"applicability", "score", "rationale", "evidence"}, item_path, errors)
            applicable = item.get("applicability") == "applicable"
            if item.get("applicability") not in {"applicable", "not_applicable"}:
                errors.append(f"{item_path}.applicability: expected 'applicable' or 'not_applicable'")
        score = item.get("score")
        rationale = item.get("rationale")
        evidence = item.get("evidence")
        if applicable:
            if not _is_int(score) or not 1 <= score <= 5:
                errors.append(f"{item_path}.score: applicable dimensions require an integer from 1 to 5")
            if version == "2.0" and item.get("applicability") != "applicable":
                pass
        elif score is not None:
            errors.append(f"{item_path}.score: not_applicable dimensions must use null")
        if not _is_text(rationale):
            errors.append(f"{item_path}.rationale: expected non-empty text")
        if not isinstance(evidence, list) or (applicable and len(evidence) < 1) or any(not isinstance(x, str) for x in (evidence if isinstance(evidence, list) else [])):
            errors.append(f"{item_path}.evidence: expected a string array" + (" with at least one item" if applicable else ""))


def validate_scorecard(document: Any) -> list[str]:
    """Return all validation errors for a v1.0 or v2.0 scorecard."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["scorecard: expected a JSON object"]
    version = document.get("schema_version")
    if version == "1.0":
        required = {
            "schema_version", "pair_id", "assessor_id", "blind_label",
            "submitted_at_utc", "dimensions", "overall_preference",
            "confidence", "notes",
        }
        _keys_error(document, required, "scorecard", errors)
        if not _is_text(document.get("pair_id")):
            errors.append("pair_id: expected non-empty text")
        if not _is_text(document.get("assessor_id")):
            errors.append("assessor_id: expected non-empty text")
        if document.get("blind_label") not in {"A", "B"}:
            errors.append("blind_label: expected A or B")
        _timestamp_error(document.get("submitted_at_utc"), "submitted_at_utc", errors)
        _validate_dimensions(document.get("dimensions"), "dimensions", "1.0", errors)
        if document.get("overall_preference") not in PREFERENCES:
            errors.append("overall_preference: invalid preference")
        confidence = document.get("confidence")
        if not _is_int(confidence) or not 1 <= confidence <= 5:
            errors.append("confidence: expected an integer from 1 to 5")
        if not isinstance(document.get("notes"), str):
            errors.append("notes: expected text")
        return errors

    if version == "2.0":
        required = {"schema_version", "pair_id", "case_id", "blind_label", "assessments"}
        _keys_error(document, required, "scorecard", errors)
        for key in ("pair_id", "case_id"):
            if not _is_text(document.get(key)):
                errors.append(f"{key}: expected non-empty text")
        if document.get("blind_label") not in {"A", "B"}:
            errors.append("blind_label: expected A or B")
        assessments = document.get("assessments")
        if not isinstance(assessments, list) or not assessments:
            errors.append("assessments: expected a non-empty array")
            return errors
        seen: set[str] = set()
        expected = {
            "assessor_id", "submitted_at_utc", "dimensions",
            "overall_preference", "confidence", "notes",
        }
        for index, assessment in enumerate(assessments):
            path = f"assessments[{index}]"
            if not isinstance(assessment, dict):
                errors.append(f"{path}: expected an object")
                continue
            _keys_error(assessment, expected, path, errors)
            assessor_id = assessment.get("assessor_id")
            if not _is_text(assessor_id):
                errors.append(f"{path}.assessor_id: expected non-empty text")
            elif assessor_id in seen:
                errors.append(f"{path}.assessor_id: duplicate assessor ID for this response")
            else:
                seen.add(assessor_id)
            _timestamp_error(assessment.get("submitted_at_utc"), f"{path}.submitted_at_utc", errors)
            _validate_dimensions(assessment.get("dimensions"), f"{path}.dimensions", "2.0", errors)
            if assessment.get("overall_preference") not in PREFERENCES:
                errors.append(f"{path}.overall_preference: invalid preference")
            confidence = assessment.get("confidence")
            if not _is_int(confidence) or not 1 <= confidence <= 5:
                errors.append(f"{path}.confidence: expected an integer from 1 to 5")
            if not isinstance(assessment.get("notes"), str):
                errors.append(f"{path}.notes: expected text")
        return errors

    return [f"schema_version: unsupported value {version!r}; expected '1.0' or '2.0'"]


def _normalize(document: dict[str, Any]) -> dict[str, Any]:
    version = document["schema_version"]
    if version == "1.0":
        assessment = {
            "assessor_id": document["assessor_id"],
            "submitted_at_utc": document["submitted_at_utc"],
            "dimensions": {
                name: {
                    "applicability": "applicable",
                    "score": item["score"],
                    "rationale": item["rationale"],
                    "evidence": item["evidence"],
                }
                for name, item in document["dimensions"].items()
            },
            "overall_preference": document["overall_preference"],
            "confidence": document["confidence"],
            "notes": document["notes"],
        }
        assessments = [assessment]
        case_id = LEGACY_CASE_ID
    else:
        assessments = document["assessments"]
        case_id = document["case_id"]
    return {
        "schema_version": version,
        "pair_id": document["pair_id"],
        "case_id": case_id,
        "blind_label": document["blind_label"],
        "assessments": assessments,
    }


def build_report(documents: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build descriptive blind-label/case/dimension summaries from valid cards."""
    response_assessors: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    dimension_rows: dict[tuple[str, str, str], list[tuple[str, str, int | None]]] = defaultdict(list)
    pair_preferences: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    pair_cases: set[tuple[str, str]] = set()
    legacy_count = 0
    v2_count = 0

    for index, document in enumerate(documents):
        errors = validate_scorecard(document)
        if errors:
            raise ScorecardValidationError(f"scorecard #{index + 1}: " + "; ".join(errors))
        normalized = _normalize(document)
        if normalized["schema_version"] == "1.0":
            legacy_count += 1
        else:
            v2_count += 1
        pair_id = normalized["pair_id"]
        case_id = normalized["case_id"]
        label = normalized["blind_label"]
        pair_cases.add((pair_id, case_id))
        response_key = (pair_id, case_id, label)

        for assessment in normalized["assessments"]:
            assessor_id = assessment["assessor_id"]
            if assessor_id in response_assessors[response_key]:
                raise ScorecardValidationError(
                    f"duplicate assessor ID {assessor_id!r} across scorecards for pair {pair_id!r}, "
                    f"case {case_id!r}, blind label {label}"
                )
            response_assessors[response_key].add(assessor_id)
            pair_preferences[(pair_id, case_id, assessor_id)][label] = assessment["overall_preference"]
            for dimension in DIMENSIONS:
                rating = assessment["dimensions"][dimension]
                score = rating["score"] if rating["applicability"] == "applicable" else None
                dimension_rows[(case_id, label, dimension)].append((pair_id, assessor_id, score))

    summary = []
    for (case_id, label, dimension), rows in sorted(dimension_rows.items()):
        scores = [score for _, _, score in rows if score is not None]
        distinct = sorted(set(scores))
        counts = {str(n): scores.count(n) for n in range(1, 6)}
        summary.append({
            "case_id": case_id,
            "blind_label": label,
            "dimension": dimension,
            "pair_count": len({pair for pair, _, _ in rows}),
            "assessment_count": len(rows),
            "assessor_count": len({(pair, assessor) for pair, assessor, _ in rows}),
            "applicable_assessment_count": len(scores),
            "not_applicable_count": len(rows) - len(scores),
            "score_counts": counts,
            "minimum": min(scores) if scores else None,
            "maximum": max(scores) if scores else None,
            "mean": round(statistics.mean(scores), 3) if scores else None,
            "median": statistics.median(scores) if scores else None,
            "score_range": (max(scores) - min(scores)) if scores else None,
            "distinct_score_count": len(distinct),
            "disagreement_observed": len(distinct) > 1,
        })

    preference_summary = []
    grouped_preferences: dict[tuple[str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for (pair_id, case_id, assessor_id), values_by_label in pair_preferences.items():
        grouped_preferences[(pair_id, case_id)][assessor_id] = values_by_label
    for (pair_id, case_id), by_assessor in sorted(grouped_preferences.items()):
        counts = {preference: 0 for preference in PREFERENCES}
        conflicts = []
        incomplete = []
        for assessor_id, values_by_label in sorted(by_assessor.items()):
            submitted_labels = sorted(values_by_label)
            if submitted_labels != ["A", "B"]:
                incomplete.append({
                    "assessor_id": assessor_id,
                    "submitted_labels": submitted_labels,
                    "missing_labels": sorted({"A", "B"} - set(submitted_labels)),
                })
                continue
            preference_a = values_by_label["A"]
            preference_b = values_by_label["B"]
            if preference_a != preference_b:
                conflicts.append({
                    "assessor_id": assessor_id,
                    "observed_preferences": {"A": preference_a, "B": preference_b},
                })
            else:
                counts[preference_a] += 1
        preference_summary.append({
            "pair_id": pair_id,
            "case_id": case_id,
            "assessor_count": sum(counts.values()),
            "incomplete_assessor_count": len(incomplete),
            "incomplete_assessments": incomplete,
            "preference_counts": counts,
            "conflicting_assessments": conflicts,
            "conflict_count": len(conflicts),
        })

    return {
        "report_version": "1.0",
        "interpretation_boundary": (
            "Summaries are descriptive only. Blind labels A/B are not mapped to treatment conditions. "
            "Agreement is not proof of correctness; score variation is not a significance test."
        ),
        "input_counts": {
            "scorecard_files": legacy_count + v2_count,
            "legacy_v1_files": legacy_count,
            "multi_assessor_v2_files": v2_count,
            "pair_case_count": len(pair_cases),
        },
        "ratings_by_blind_label_case_dimension": summary,
        "pair_preferences": preference_summary,
    }


def _input_files(values: list[str]) -> list[Path]:
    files: list[Path] = []
    for value in values:
        path = Path(value)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.json")
                                if p.name.startswith("scorecard-") and p.name not in {"scorecard-template.json", "scorecard-report.json"}))
        else:
            raise FileNotFoundError(value)
    unique = list(dict.fromkeys(p.resolve() for p in files))
    if not unique:
        raise FileNotFoundError("no scorecard JSON files found")
    return unique


def _read_files(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    documents = []
    errors = []
    for path in paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue
        validation = validate_scorecard(document)
        if validation:
            errors.extend(f"{path}: {message}" for message in validation)
        else:
            documents.append(document)
    return documents, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate", help="Validate v1.0 and v2.0 scorecards.")
    validate_parser.add_argument("inputs", nargs="+", help="Scorecard JSON files or directories.")
    report_parser = commands.add_parser("report", help="Generate descriptive multi-assessor summaries.")
    report_parser.add_argument("inputs", nargs="+", help="Scorecard JSON files or directories.")
    report_parser.add_argument("--out", required=True, help="Output JSON report path.")
    args = parser.parse_args(argv)

    try:
        paths = _input_files(args.inputs)
        documents, errors = _read_files(paths)
        if errors:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
            return 1
        if args.command == "validate":
            print(json.dumps({"valid": True, "scorecard_files": len(paths),
                              "schema_versions": sorted({doc["schema_version"] for doc in documents})}, indent=2))
            return 0
        report = build_report(documents)
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"valid": True, "scorecard_files": len(paths), "report": str(output)}, indent=2))
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
