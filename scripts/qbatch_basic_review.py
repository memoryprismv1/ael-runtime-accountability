#!/usr/bin/env python3
"""Basic offline review for Q-Batch evidence records.

This is a lightweight integrity/consistency check, not a semantic peer review
and not a substitute for the experiment's full acceptance gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def review(record_path: Path, log_path: Path) -> list[tuple[str, str, str]]:
    """Return (severity, finding, detail) tuples for one evidence record."""
    findings: list[tuple[str, str, str]] = []
    try:
        record = load_json(record_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [("BLOCKER", "Evidence record unreadable", str(exc))]

    if not log_path.is_file():
        findings.append(("BLOCKER", "Raw log missing", str(log_path)))
        return findings

    log_bytes = log_path.read_bytes()
    actual_hash = hashlib.sha256(log_bytes).hexdigest()
    expected_hash = record.get("execution", {}).get("log_sha256")
    if not expected_hash:
        outputs = record.get("outputs", [])
        if isinstance(outputs, list):
            for output in outputs:
                if isinstance(output, dict) and output.get("path") == log_path.name:
                    expected_hash = output.get("sha256")
                    break
    if not expected_hash:
        findings.append(("BLOCKER", "Log hash absent", "No expected SHA-256 found in execution or outputs."))
    elif expected_hash != actual_hash:
        findings.append(("BLOCKER", "Log hash mismatch", f"Expected {expected_hash}; observed {actual_hash}."))
    else:
        findings.append(("PASS", "Raw log hash matches", actual_hash))

    execution = record.get("execution", {})
    exit_code = execution.get("exit_code")
    status = record.get("status")
    tests_reported = execution.get("tests_reported")
    if exit_code != 0 or status != "passed":
        findings.append(("BLOCKER", "Run did not pass", f"status={status!r}; exit_code={exit_code!r}."))
    else:
        findings.append(("PASS", "Run status passed", "Structured status and process exit code agree."))

    log_text = log_bytes.decode("utf-8", errors="replace")
    if tests_reported is None or "Ran " not in log_text or "OK" not in log_text:
        findings.append(("BLOCKER", "Test summary not corroborated", "Expected a unittest summary with a test count and OK in the raw log."))
    else:
        findings.append(("PASS", "Test summary present", f"Structured test count: {tests_reported}."))

    if record.get("schema_version") is None:
        findings.append(("WARNING", "Schema version missing", "Record cannot be interpreted against a declared schema version."))
    if not record.get("batch_id"):
        findings.append(("WARNING", "Batch identifier missing", "Evidence is harder to trace to a unique attempt."))
    if record.get("execution", {}).get("real_model_inference_performed") is False:
        findings.append(("INFO", "Mocked/unit evidence only", "This batch does not establish real-model behaviour or task effectiveness."))

    return findings


def render_report(record_path: Path, findings: list[tuple[str, str, str]]) -> str:
    lines = [
        "# Q-Batch Basic Evidence Review",
        "",
        f"- Evidence record: `{record_path}`",
        "- Review type: automated integrity and consistency checks",
        "- Limitation: this does not judge semantic quality or establish experimental efficacy.",
        "",
        "## Findings",
        "",
    ]
    for severity, finding, detail in findings:
        lines.extend([f"### {severity}: {finding}", "", detail, ""])
    blockers = sum(1 for severity, _, _ in findings if severity == "BLOCKER")
    lines.extend([
        "## Outcome",
        "",
        f"**{'BLOCKED' if blockers else 'BASIC CHECKS PASSED'}** — {blockers} blocking finding(s).",
        "",
        "A passing result means only that the checks implemented here passed. Apply the experiment-specific acceptance gate before treating a pair as valid.",
        "",
        "For deeper review, use the [Peer Review skill](https://github.com/memoryprismv1/cognitive-interface-ai-skills/tree/main/peer-review). It is optional; this basic review does not require it.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", required=True, type=Path, help="Structured JSON evidence record")
    parser.add_argument("--log", required=True, type=Path, help="Raw log referenced by the evidence record")
    parser.add_argument("--report", type=Path, help="Optional Markdown report output path")
    args = parser.parse_args()

    findings = review(args.record, args.log)
    report = render_report(args.record, findings)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
    print(report)
    return 1 if any(severity == "BLOCKER" for severity, _, _ in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
