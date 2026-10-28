"""Validate run manifests, chained JSONL events, and referenced evidence."""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from .logger import SCHEMA_VERSION, LOGGER_VERSION, canonical_json, sha256_bytes, sha256_file

PHASES = {"setup", "planning", "implementation", "debugging", "verification", "delivery", "preflight"}
ACTORS = {"runner", "agent", "tool", "runtime", "reviewer", "logger"}
EVENT_TYPES = {"run_started", "run_finished", "plan_submitted", "phase_started", "agent_note", "tool_call", "model_request_started", "model_request_succeeded", "model_request_failed", "model_request", "model_response", "command_started", "command_finished", "test_result", "requirement_check", "commit_created", "file_changed", "artifact_captured", "preflight_check", "error", "retry", "agent_recovery_attempt", "agent_loop_detected"}
STATUSES = {"started", "succeeded", "failed", "observed", "declared", "skipped", "requested"}
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
MANIFEST_FIELDS = {"run_id", "condition_label", "task_brief_sha256", "condition_config_sha256", "logger_version", "schema_version", "started_at_utc", "model", "environment", "resource_limits", "base_commit"}


class LogValidationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise LogValidationError(message)


def _iso_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value.endswith("Z") or "+" in value[10:]
    except ValueError:
        return False


def _hash_ref(run_dir: Path, ref: Any) -> None:
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256", "size_bytes"}:
        _fail("evidence reference must have exactly path, sha256, and size_bytes")
    if not isinstance(ref["path"], str) or not ref["path"] or Path(ref["path"]).is_absolute() or ".." in Path(ref["path"]).parts:
        _fail("unsafe evidence path")
    if not HASH_RE.fullmatch(str(ref["sha256"])):
        _fail("invalid evidence SHA-256")
    if not isinstance(ref["size_bytes"], int) or ref["size_bytes"] < 0:
        _fail("invalid evidence size")
    root = run_dir.resolve(strict=True)
    path = (run_dir / ref["path"]).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError:
        _fail("evidence path escapes run directory")
    if not path.is_file():
        _fail(f"evidence is not a file: {ref['path']}")
    if path.stat().st_size != ref["size_bytes"]:
        _fail(f"evidence size mismatch: {ref['path']}")
    if sha256_file(path) != ref["sha256"]:
        _fail(f"evidence hash mismatch: {ref['path']}")


def validate_run(run_dir: str | Path, require_finished: bool = True) -> dict[str, Any]:
    root = Path(run_dir).resolve(strict=True)
    manifest_path = root / "manifest.json"
    events_path = root / "events.jsonl"
    if not manifest_path.is_file() or not events_path.is_file():
        _fail("missing manifest.json or events.jsonl")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail(f"invalid manifest JSON: {exc}")
    if not isinstance(manifest, dict) or MANIFEST_FIELDS - set(manifest):
        _fail(f"manifest missing fields: {sorted(MANIFEST_FIELDS - set(manifest if isinstance(manifest, dict) else {}))}")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["logger_version"] != LOGGER_VERSION:
        _fail("unsupported schema/logger version")
    if manifest["condition_label"] not in {"A", "B", "REHEARSAL-A", "REHEARSAL-B"}:
        _fail("invalid condition label")
    if not HASH_RE.fullmatch(str(manifest["task_brief_sha256"])):
        _fail("invalid task brief hash")
    if not HASH_RE.fullmatch(str(manifest["condition_config_sha256"])):
        _fail("invalid condition configuration hash")
    if not _iso_time(manifest["started_at_utc"]):
        _fail("invalid manifest timestamp")
    for obj in (manifest["model"], manifest["environment"], manifest["resource_limits"]):
        if not isinstance(obj, dict):
            _fail("model, environment and resource_limits must be objects")
    raw_lines = events_path.read_bytes().splitlines()
    if not raw_lines:
        _fail("event log is empty")
    expected_seq = 1
    prev_hash = None
    event_types: set[str] = set()
    referenced = 0
    parsed: list[dict[str, Any]] = []
    for line_number, raw in enumerate(raw_lines, start=1):
        try:
            event = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            _fail(f"line {line_number}: invalid JSON: {exc}")
        required = {"schema_version", "run_id", "seq", "timestamp_utc", "phase", "actor", "event_type", "status", "payload", "evidence_refs", "prev_event_sha256", "event_sha256"}
        if not isinstance(event, dict) or set(event) != required:
            _fail(f"line {line_number}: event fields differ from schema")
        if event["schema_version"] != SCHEMA_VERSION or event["run_id"] != manifest["run_id"]:
            _fail(f"line {line_number}: schema/run ID mismatch")
        if event["seq"] != expected_seq:
            _fail(f"line {line_number}: expected seq {expected_seq}, got {event['seq']}")
        if not _iso_time(event["timestamp_utc"]):
            _fail(f"line {line_number}: invalid UTC timestamp")
        if event["phase"] not in PHASES or event["actor"] not in ACTORS or event["event_type"] not in EVENT_TYPES or event["status"] not in STATUSES:
            _fail(f"line {line_number}: unknown enum value")
        if not isinstance(event["payload"], dict) or not isinstance(event["evidence_refs"], list):
            _fail(f"line {line_number}: invalid payload/evidence_refs types")
        if event["prev_event_sha256"] != prev_hash:
            _fail(f"line {line_number}: broken event hash chain")
        supplied_hash = event["event_sha256"]
        unhashed = dict(event)
        unhashed.pop("event_sha256")
        actual_hash = sha256_bytes(canonical_json(unhashed))
        if supplied_hash != actual_hash:
            _fail(f"line {line_number}: event hash mismatch")
        for ref in event["evidence_refs"]:
            _hash_ref(root, ref)
            referenced += 1
        prev_hash = supplied_hash
        expected_seq += 1
        event_types.add(event["event_type"])
        parsed.append(event)
    if parsed[0]["event_type"] != "run_started":
        _fail("first event must be run_started")
    if require_finished and parsed[-1]["event_type"] != "run_finished":
        _fail("last event must be run_finished")
    checksum_path = root / "checksums.sha256"
    if not checksum_path.is_file():
        _fail("missing checksums.sha256")
    first = checksum_path.read_text(encoding="ascii").split()
    if len(first) != 2 or first[1] != "events.jsonl" or first[0] != sha256_file(events_path):
        _fail("events.jsonl checksum missing, malformed, or mismatched")
    return {"run_id": manifest["run_id"], "condition_label": manifest["condition_label"], "events": len(parsed), "event_types": sorted(event_types), "evidence_refs_verified": referenced, "events_sha256": sha256_file(events_path), "status": parsed[-1]["payload"].get("completion_status", parsed[-1]["status"])}


def validate_pair(run_a: str | Path, run_b: str | Path, required_event_types: set[str] | None = None) -> dict[str, Any]:
    a, b = validate_run(run_a), validate_run(run_b)
    if a["condition_label"] not in {"A", "REHEARSAL-A"} or b["condition_label"] not in {"B", "REHEARSAL-B"}:
        _fail("pair must be passed in A then B order")
    if a["run_id"] == b["run_id"]:
        _fail("paired runs must have distinct run IDs")
    ma = json.loads((Path(run_a) / "manifest.json").read_text(encoding="utf-8"))
    mb = json.loads((Path(run_b) / "manifest.json").read_text(encoding="utf-8"))
    shared = ["task_brief_sha256", "logger_version", "schema_version", "model", "environment", "resource_limits", "base_commit", "client_brief_sha256", "api_contract_sha256", "starter_sha256", "acceptance_suite_sha256", "acceptance_contract_version"]
    mismatches = [field for field in shared if ma.get(field) != mb.get(field)]
    if mismatches:
        _fail(f"paired run manifests differ on controlled fields: {mismatches}")
    required = required_event_types or {"run_started", "run_finished", "plan_submitted", "tool_call", "model_request", "model_response", "command_started", "command_finished", "test_result", "file_changed"}
    for label, report in (("A", a), ("B", b)):
        missing = sorted(required - set(report["event_types"]))
        if missing:
            _fail(f"run {label} missing required event types: {missing}")
    return {"status": "PASS", "run_a": a, "run_b": b, "controlled_manifest_fields_match": shared, "required_event_types": sorted(required), "pairing_note": "Instrumentation validation only; this does not score software quality or establish skill efficacy."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="One run directory to validate")
    args = parser.parse_args()
    try:
        report = validate_run(args.run_dir)
    except (LogValidationError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "PASS", **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
