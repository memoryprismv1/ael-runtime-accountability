"""Generate an UNSCORED instrumentation rehearsal and a machine-readable gate report.

This checks the logger and evidence path only. Rehearsal results are not model
outputs and must never be used as evidence of Critical Thinking skill efficacy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .logger import LOGGER_VERSION, SCHEMA_VERSION, RunLogger, utc_now
from .validate_log import LogValidationError, validate_pair

REHEARSAL_BRIEF = "Instrumentation rehearsal: submit a plan, change a file, record a failing command, recover, and capture a test result. No software product is being evaluated."


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest(label: str, suffix: str, workspaces: Path, task_sha: str) -> dict[str, Any]:
    return {
        "run_id": f"rehearsal-{label.lower()}-{suffix}",
        "condition_label": f"REHEARSAL-{label}",
        "task_brief_sha256": task_sha,
        "condition_config_sha256": _sha(f"synthetic-preflight-condition:{label}"),
        "logger_version": LOGGER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "started_at_utc": utc_now(),
        "model": {"provider": "synthetic-rehearsal", "model_id": "none", "version": "none"},
        "environment": {"runtime": f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "platform": sys.platform},
        "resource_limits": {"timeout_seconds_per_command": 10, "network": "not_used"},
        "base_commit": "not-applicable-rehearsal"
    }


def run_rehearsal(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"rehearsal output must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    task_hash = _sha(REHEARSAL_BRIEF)
    for label in ("A", "B"):
        workspace = output / "workspaces" / label
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "starter.txt").write_text("baseline\n", encoding="utf-8")
        run_dir = output / f"run-{label.lower()}"
        manifest = _manifest(label, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"), workspace, task_hash)
        logger = RunLogger(run_dir, workspace, manifest)
        try:
            logger.record_agent_plan("1. Inspect the starter file. 2. Attempt a command that fails. 3. Record the failure and recover. 4. Change the file, run a passing check, and report evidence.")
            logger.record_model_exchange({"provider": "synthetic-rehearsal", "model_id": "none", "request_id": "preflight-1", "latency_ms": 0}, "SYNTHETIC PREFLIGHT PROMPT: validate raw request capture", "SYNTHETIC PREFLIGHT RESPONSE: raw response capture is operational", {"input_tokens": 0, "output_tokens": 0}, phase="planning")
            logger.record_tool_call("preflight_fixture", f"rehearsal-{label.lower()}", {"action": "synthetic_capture_check"}, {"status": "ok"}, status="succeeded", phase="preflight")
            before = logger.snapshot_workspace()
            (workspace / "starter.txt").write_text(f"baseline\nrehearsal condition {label}\n", encoding="utf-8")
            logger.record_file_changes(before, logger.snapshot_workspace())
            created = logger.run_command([sys.executable, "-c", "from pathlib import Path; Path('from-command.txt').write_text('captured by workspace diff')"], workspace, "implementation", timeout_seconds=10)
            if created.returncode != 0:
                raise RuntimeError("file-creation rehearsal command unexpectedly failed")
            failed = logger.run_command([sys.executable, "-c", "import sys; print('intentional rehearsal failure'); sys.exit(7)"], workspace, "debugging", timeout_seconds=10)
            logger.emit("error", "runtime", "debugging", "observed", {"kind": "process_exit", "exit_code": failed.returncode, "expected_in_rehearsal": True})
            logger.emit("retry", "runner", "debugging", "observed", {"reason": "rehearsal validates recovery trace", "retry_of_exit_code": failed.returncode})
            recovered = logger.run_command([sys.executable, "-c", "print('recovery succeeded')"], workspace, "debugging", timeout_seconds=10)
            check_ref = logger.capture_artifact("check-result.txt", "PASS: recovery command returned exit code 0\n", "text/plain; charset=utf-8")
            logger.record_test_result([sys.executable, "-c", "print('PASS')"], recovered.returncode, 1, 0, [check_ref])
            logger.record_agent_note("Recovery followed the intentionally failed command. This is an agent-declared rehearsal note, not an efficacy claim.", "delivery", "recovery_summary")
            logger.finish("succeeded", "Synthetic instrumentation rehearsal only; not a scored model run.")
        except Exception:
            logger.close()
            raise
    report = validate_pair(output / "run-a", output / "run-b")
    run_events = {label: [json.loads(line) for line in (output / f"run-{label.lower()}" / "events.jsonl").read_text(encoding="utf-8").splitlines()] for label in ("A", "B")}
    failure_recovery_ok = all(
        any(e["event_type"] == "command_finished" and e["status"] == "failed" and e["payload"].get("exit_code") == 7 for e in events)
        and any(e["event_type"] == "error" for e in events)
        and any(e["event_type"] == "retry" for e in events)
        and any(e["event_type"] == "command_finished" and e["status"] == "succeeded" for e in events)
        and any(e["event_type"] == "test_result" and e["status"] == "succeeded" for e in events)
        for events in run_events.values()
    )
    separated = all(
        not (workspace.resolve() == run_dir.resolve() or workspace.resolve() in run_dir.resolve().parents or run_dir.resolve() in workspace.resolve().parents)
        for label in ("A", "B")
        for workspace, run_dir in [(output / "workspaces" / label, output / f"run-{label.lower()}")]
    )
    verified_refs = report["run_a"]["evidence_refs_verified"] + report["run_b"]["evidence_refs_verified"]
    checks = [
        {"id": "both_runs_valid", "status": "PASS", "evidence": "Both event streams, run manifests and event hash chains validated."},
        {"id": "controlled_fields_match", "status": "PASS", "evidence": ", ".join(report["controlled_manifest_fields_match"])},
        {"id": "failure_and_recovery_captured", "status": "PASS" if failure_recovery_ok else "FAIL", "evidence": "Both runs contain a failed command exit (7), error and retry events, a successful recovery command, and a passing test result."},
        {"id": "command_file_changes_captured", "status": "PASS" if all(any(e["event_type"] == "file_changed" and e["payload"].get("path") == "from-command.txt" and e["payload"].get("action") == "created" for e in events) for events in run_events.values()) else "FAIL", "evidence": "Each run records a source file created as a side effect of a logged command."},
        {"id": "model_and_tool_capture", "status": "PASS" if all({"tool_call", "model_request", "model_response"}.issubset({e["event_type"] for e in events}) for events in run_events.values()) else "FAIL", "evidence": "Both logs preserve a synthetic request/response pair and a synthetic tool call with referenced artifacts."},
        {"id": "workspace_log_separation", "status": "PASS" if separated else "FAIL", "evidence": "Run output and agent workspace resolve to disjoint directories."},
        {"id": "evidence_hashes_verified", "status": "PASS", "evidence": f"Verified {verified_refs} evidence references across both runs."},
        {"id": "synthetic_not_scored", "status": "PASS", "evidence": "Rehearsal uses synthetic commands and contains no model output or quality score."}
    ]
    final = {"report_version": "1.0", "created_at_utc": utc_now(), "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL", "purpose": "Instrumentation preflight only; not a Critical Thinking skill efficacy result.", "checks": checks, "pair_report": report}
    (output / "preflight-report.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New or empty output directory, outside any agent workspace")
    args = parser.parse_args()
    try:
        report = run_rehearsal(args.output)
    except (OSError, ValueError, LogValidationError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
