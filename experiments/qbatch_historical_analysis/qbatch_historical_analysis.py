#!/usr/bin/env python3
"""Read-only historical Q-Batch evidence reader and conservative cohort analyser."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import defaultdict, Counter
from pathlib import Path, PurePosixPath

MIN_COHORT_SIZE = 4
EVENT_KEYS = {"schema_version", "run_id", "seq", "timestamp_utc", "phase", "actor",
              "event_type", "status", "payload", "evidence_refs", "prev_event_sha256", "event_sha256"}
KNOWN_EVENTS = {"run_started", "run_finished", "plan_submitted", "phase_started", "agent_note",
                "tool_call", "model_request_started", "model_request_succeeded", "model_request_failed",
                "model_request", "model_response", "command_started", "command_finished", "test_result",
                "requirement_check", "commit_created", "file_changed", "artifact_captured",
                "preflight_check", "error", "retry", "agent_recovery_attempt", "agent_loop_detected"}
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
REVISION_RE = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
PROVENANCE_FIELDS = {"capture_profile", "capture_profile_sha256", "runner_implementation_revision", "runner_worktree_clean"}

def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def safe_artifact(root, relative):
    p = PurePosixPath(relative)
    if not relative or p.is_absolute() or ".." in p.parts or "\\" in relative:
        raise ValueError(f"unsafe evidence path: {relative!r}")
    target = (root / Path(*p.parts)).resolve(strict=True)
    target.relative_to(root.resolve(strict=True))
    if not target.is_file():
        raise ValueError(f"evidence is not a file: {relative}")
    return target

def infer_profile(manifest, events):
    types = {e["event_type"] for e in events}
    unknown = types - KNOWN_EVENTS
    features = {
        "context_snapshot": bool(manifest.get("context_id") and isinstance(manifest.get("context"), dict)),
        "request_lifecycle": bool(types & {"model_request_started", "model_request_succeeded", "model_request_failed"}),
        "recovery_events": bool(types & {"agent_recovery_attempt", "agent_loop_detected"}),
        "tool_dispatch": "tool_call" in types,
        "model_exchange": {"model_request", "model_response"} <= types,
        "model_transport_failure": ("model_request_failed" in types or any(e["event_type"] == "error" and e["payload"].get("kind") == "model_request_failed" for e in events)),
    }
    if unknown:
        profile = "unsupported-unknown-event-vocabulary"
    elif features["context_snapshot"] and features["request_lifecycle"]:
        profile = "context-and-request-lifecycle"
    elif features["request_lifecycle"]:
        profile = "request-lifecycle-without-context"
    elif features["tool_dispatch"] and features["model_exchange"]:
        profile = "legacy-with-tool-dispatch"
    elif features["model_transport_failure"]:
        profile = "legacy-transport-failure-only"
    elif features["model_exchange"]:
        profile = "legacy-model-exchange-only"
    elif "model_request_failed" in types or any(
        e["event_type"] == "error" and e["payload"].get("kind") == "model_request_failed" for e in events
    ):
        profile = "legacy-transport-failure-only"
    else:
        profile = "legacy-basic-observation"
    return {"profile": profile, "features": features, "unknown_event_types": sorted(unknown),
            "schema_version_label": manifest.get("schema_version"),
            "logger_version_label": manifest.get("logger_version"),
            "profile_inference": "inferred from recorded evidence; not an explicit producer identity"}


def validate_optional_provenance(manifest, start_payload):
    """Validate explicit provenance when present; old manifests remain readable."""
    present = PROVENANCE_FIELDS.intersection(manifest)
    binding_fields = {
        "capture_profile_id", "capture_profile_version", "capture_profile_sha256",
        "runner_implementation_revision", "runner_worktree_clean",
    }
    start_present = binding_fields.intersection(start_payload)
    if not present and not start_present:
        return None
    missing = PROVENANCE_FIELDS - set(manifest)
    missing_bindings = binding_fields - set(start_payload)
    if missing or missing_bindings:
        raise ValueError(
            "incomplete run provenance: "
            f"manifest={sorted(missing)}, run_started={sorted(missing_bindings)}"
        )
    profile = manifest["capture_profile"]
    if not isinstance(profile, dict) or set(profile) != {"id", "version", "capabilities"}:
        raise ValueError("capture profile must contain exactly id, version, and capabilities")
    capabilities = profile["capabilities"]
    if (not isinstance(profile["id"], str) or not profile["id"]
            or not isinstance(profile["version"], int) or profile["version"] < 1
            or not isinstance(capabilities, list) or not capabilities
            or any(not isinstance(item, str) or not item for item in capabilities)
            or len(capabilities) != len(set(capabilities))):
        raise ValueError("invalid capture profile structure")
    profile_hash = manifest["capture_profile_sha256"]
    if not isinstance(profile_hash, str) or not HASH_RE.fullmatch(profile_hash):
        raise ValueError("invalid capture profile hash")
    if profile_hash != sha256_bytes(canonical_bytes(profile)):
        raise ValueError("capture profile hash mismatch")
    revision = manifest["runner_implementation_revision"]
    if revision is not None and (not isinstance(revision, str) or not REVISION_RE.fullmatch(revision)):
        raise ValueError("invalid runner implementation revision")
    clean = manifest["runner_worktree_clean"]
    if clean is not None and not isinstance(clean, bool):
        raise ValueError("runner worktree clean state must be boolean or null")
    expected = {
        "capture_profile_id": profile["id"],
        "capture_profile_version": profile["version"],
        "capture_profile_sha256": profile_hash,
        "runner_implementation_revision": revision,
        "runner_worktree_clean": clean,
    }
    for field, value in expected.items():
        if start_payload.get(field) != value:
            raise ValueError(f"run provenance {field} is not bound to run_started")
    return {
        "capture_profile_id": profile["id"],
        "capture_profile_version": profile["version"],
        "capture_profile_sha256": profile_hash,
        "runner_implementation_revision": revision,
        "runner_worktree_clean": clean,
    }

def read_run(root, attempt_id):
    root = Path(root).resolve(strict=True)
    mp, ep = root / "manifest.json", root / "events.jsonl"
    if not mp.is_file() or not ep.is_file():
        raise ValueError("missing manifest.json or events.jsonl")
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or manifest.get("logger_version") != "0.1.0":
        raise ValueError("unsupported schema/logger labels")
    lines = ep.read_bytes().splitlines()
    if not lines:
        raise ValueError("empty event stream")
    events, previous, refs = [], None, 0
    for seq, line in enumerate(lines, 1):
        event = json.loads(line.decode("utf-8"))
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            raise ValueError(f"event {seq}: unsupported event envelope")
        if event["seq"] != seq or event["run_id"] != manifest.get("run_id"):
            raise ValueError(f"event {seq}: sequence or run identity mismatch")
        if event["schema_version"] != manifest["schema_version"] or event["prev_event_sha256"] != previous:
            raise ValueError(f"event {seq}: schema or hash-chain mismatch")
        if not isinstance(event["payload"], dict) or not isinstance(event["evidence_refs"], list):
            raise ValueError(f"event {seq}: invalid payload/evidence_refs")
        unhashed = dict(event)
        supplied = unhashed.pop("event_sha256")
        if supplied != sha256_bytes(canonical_bytes(unhashed)):
            raise ValueError(f"event {seq}: event hash mismatch")
        for ref in event["evidence_refs"]:
            if not isinstance(ref, dict) or set(ref) != {"path", "sha256", "size_bytes"}:
                raise ValueError(f"event {seq}: malformed evidence reference")
            artifact = safe_artifact(root, ref["path"])
            if artifact.stat().st_size != ref["size_bytes"] or not HASH_RE.fullmatch(str(ref["sha256"])) or sha256_file(artifact) != ref["sha256"]:
                raise ValueError(f"event {seq}: evidence size/hash mismatch: {ref['path']}")
            refs += 1
        events.append(event)
        previous = supplied
    if events[0]["event_type"] != "run_started":
        raise ValueError("first event is not run_started")
    context = manifest.get("context")
    if context is not None:
        start = events[0]["payload"]
        if manifest.get("context_id") != context.get("context_id") or start.get("context_id") != context.get("context_id") or start.get("context_sha256") != sha256_bytes(canonical_bytes(context)):
            raise ValueError("context snapshot is not bound to run_started")
    run_provenance = validate_optional_provenance(manifest, events[0]["payload"])
    checksum = root / "checksums.sha256"
    checksum_status = "not_present"
    if checksum.exists():
        fields = checksum.read_text(encoding="ascii").split()
        if len(fields) < 2 or fields[1] != "events.jsonl" or fields[0] != sha256_file(ep):
            raise ValueError("events.jsonl checksum mismatch")
        checksum_status = "verified"
    profile = infer_profile(manifest, events)
    return {"root": root, "attempt_id": attempt_id, "manifest": manifest, "events": events,
            "condition_label": manifest.get("condition_label"), "run_id": manifest.get("run_id"),
            "event_types": {e["event_type"] for e in events}, "format_profile": profile,
            "run_provenance": run_provenance,
            "integrity": {"status": "PASS" if checksum_status == "verified" else "PARTIAL",
                          "events": len(events), "evidence_refs_verified": refs,
                          "checksum": checksum_status, "events_sha256": sha256_file(ep)}}

def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def classify_failure(run):
    root, events = run["root"], run["events"]
    if run["format_profile"]["unknown_event_types"]:
        return {"signature": "unclassified_unsupported_event_vocabulary", "stage": "unknown", "observed": {}}
    errors = [e["payload"] for e in events if e["event_type"] == "error"]
    transport = [p for p in errors if p.get("kind") == "model_request_failed"]
    if transport:
        first = all(p.get("turn") == 1 for p in transport)
        timeout = any("timeout" in (str(p.get("error_type", "")) + str(p.get("message", ""))).lower() for p in transport)
        return {"signature": "first_request_timeout" if first and timeout else "model_request_transport_failure",
                "stage": "model_transport", "observed": {"failed_requests": len(transport), "first_turn_only": first}}
    tool_calls, rejected, rejected_evidence = 0, 0, []
    tool_names = Counter()
    for event in events:
        if event["event_type"] != "tool_call":
            continue
        tool_calls += 1
        tool_names[event["payload"].get("tool_name", "<missing>")] += 1
        for ref in event["evidence_refs"]:
            p = safe_artifact(root, ref["path"])
            data = _read_json(p)
            if isinstance(data, dict) and "plan may be submitted only once" in str(data.get("message", "")):
                rejected += 1
                rejected_evidence.append({"path": ref["path"], "sha256": ref["sha256"]})
    if rejected >= 2:
        return {"signature": "rejected_plan_resubmission_loop", "stage": "tool_execution",
                "observed": {"tool_call_count": tool_calls, "rejected_plan_submissions": rejected,
                             "tool_name_counts": dict(sorted(tool_names.items()))},
                "evidence_artifacts": rejected_evidence}
    no_tool = [p for p in errors if p.get("kind") == "model_response_without_tool_call"]
    response_files = list((root / "artifacts").glob("*model-response*")) if (root / "artifacts").exists() else []
    encoded, encoded_refs = 0, []
    for path in response_files:
        data = _read_json(path)
        content = data.get("message", {}).get("content") if isinstance(data, dict) else None
        if not isinstance(content, str):
            continue
        candidate = content.strip()
        if candidate.startswith(chr(96) * 3 + "json") and candidate.endswith(chr(96) * 3):
            candidate = candidate[7:-3].strip()
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("name"), str) and "arguments" in obj:
            encoded += 1
            encoded_refs.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)})
    if encoded >= 4 and tool_calls == 0:
        return {"signature": "text_encoded_tool_calls_not_dispatched", "stage": "model_response_protocol",
                "observed": {"json_encoded_tool_responses": encoded, "response_artifacts": len(response_files),
                             "dispatched_tool_calls": 0}, "evidence_artifacts": encoded_refs}
    if len(no_tool) >= 4:
        return {"signature": "repeated_no_tool_responses", "stage": "agent_control",
                "observed": {"no_tool_response_events": len(no_tool), "dispatched_tool_calls": tool_calls},
                "source_event_seqs": [e["seq"] for e in events if e["event_type"] == "error" and e["payload"].get("kind") == "model_response_without_tool_call"]}
    if any("did not call finish" in str(p.get("message", "")) for p in errors):
        return {"signature": "turn_budget_exhaustion_unclassified", "stage": "agent_control",
                "observed": {"dispatched_tool_calls": tool_calls}}
    return {"signature": "unclassified_failure", "stage": "unknown",
            "observed": {"error_events": len(errors), "dispatched_tool_calls": tool_calls}}

def normalise(run, attempt_url=None):
    m = run["manifest"]
    model = m.get("model", {}) if isinstance(m.get("model"), dict) else {}
    env = m.get("environment", {}) if isinstance(m.get("environment"), dict) else {}
    limits = m.get("resource_limits", {}) if isinstance(m.get("resource_limits"), dict) else {}
    opts = limits.get("options", {}) if isinstance(limits.get("options"), dict) else {}
    identity = {
        "task_brief_sha256": m.get("task_brief_sha256"), "client_brief_sha256": m.get("client_brief_sha256"),
        "api_contract_sha256": m.get("api_contract_sha256"), "starter_sha256": m.get("starter_sha256"),
        "acceptance_suite_sha256": m.get("acceptance_suite_sha256"), "acceptance_contract_version": m.get("acceptance_contract_version"),
        "base_commit": m.get("base_commit"), "runner_implementation_revision": m.get("runner_implementation_revision"),
        "runner_worktree_clean": m.get("runner_worktree_clean"),
        "capture_profile_id": (m.get("capture_profile") or {}).get("id") if isinstance(m.get("capture_profile"), dict) else None,
        "capture_profile_version": (m.get("capture_profile") or {}).get("version") if isinstance(m.get("capture_profile"), dict) else None,
        "capture_profile_sha256": m.get("capture_profile_sha256"),
        "model_id": model.get("model_id"), "model_digest": model.get("model_digest"), "provider": model.get("provider"),
        "ollama_version": env.get("ollama_version", model.get("ollama_version")), "temperature": opts.get("temperature"),
        "num_ctx": opts.get("num_ctx"), "num_predict": opts.get("num_predict"), "max_turns": limits.get("max_turns"),
        "max_tool_calls": limits.get("max_tool_calls"), "tool_version": limits.get("tool_version"),
        "request_timeout_seconds": limits.get("timeout_seconds_per_model_request"),
    }
    required = ["task_brief_sha256", "client_brief_sha256", "api_contract_sha256", "starter_sha256",
                "acceptance_suite_sha256", "base_commit", "runner_implementation_revision",
                "capture_profile_id", "capture_profile_version", "capture_profile_sha256", "model_id",
                "model_digest", "ollama_version", "max_turns", "max_tool_calls", "temperature", "num_ctx",
                "num_predict", "request_timeout_seconds"]
    missing = [k for k in required if identity.get(k) in (None, "")]
    if identity["runner_worktree_clean"] is not True:
        missing.append("runner_worktree_clean=true")
    failure = classify_failure(run)
    run_num = re.search(r"(\d{8,})", run["attempt_id"])
    url = attempt_url or (f"https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/{run_num.group(1)}" if run_num else None)
    return {"attempt_id": run["attempt_id"], "source_run_url": url, "run_id": run["run_id"],
            "condition_label": run["condition_label"], "format_profile": run["format_profile"],
            "run_provenance": run.get("run_provenance"), "integrity": run["integrity"], "task_identity": identity,
            "task_identity_hash": sha256_bytes(canonical_bytes(identity)), "identity_complete": not missing,
            "missing_identity_fields": missing, "failure": failure}

def analyse_cohorts(records, min_size=MIN_COHORT_SIZE):
    by_attempt = defaultdict(list)
    for row in records:
        by_attempt[row["attempt_id"]].append(row)
    attempts, groups = [], defaultdict(list)
    for attempt_id, rows in sorted(by_attempt.items()):
        signatures = sorted({r["failure"]["signature"] for r in rows})
        identities = {r["task_identity_hash"] for r in rows}
        profiles = {r["format_profile"]["profile"] for r in rows}
        paired = {r["condition_label"] for r in rows} >= {"A", "B"}
        complete = all(r.get("identity_complete", False) for r in rows)
        coherent = len(signatures) == len(identities) == len(profiles) == 1 and paired
        sig = signatures[0] if coherent else "mixed_or_incomplete_pair"
        ident = next(iter(identities)) if coherent else None
        profile = next(iter(profiles)) if coherent else None
        attempt = {"attempt_id": attempt_id, "source_run_url": rows[0].get("source_run_url"),
                   "run_count": len(rows), "conditions": [r["condition_label"] for r in rows],
                   "failure_signatures": signatures, "signature": sig, "task_identity_hash": ident,
                   "format_profile": profile, "identity_complete": complete, "paired_A_B": paired,
                   "status": "coherent_attempt" if coherent else "inconclusive_pair",
                   "missing_identity_fields": sorted({f for r in rows for f in r.get("missing_identity_fields", [])})}
        attempts.append(attempt)
        if coherent:
            groups[(sig, ident, profile)].append(attempt)
    cohorts = []
    for (signature, identity, profile), members in sorted(groups.items()):
        count = len(members)
        complete = all(a["identity_complete"] for a in members)
        status = "ineligible_missing_comparability_metadata" if not complete else (
            "threshold_met_for_diagnosis" if count >= min_size else "insufficient_comparable_attempts")
        cohorts.append({"failure_signature": signature, "task_identity_hash": identity, "format_profile": profile,
                        "attempt_ids": [a["attempt_id"] for a in members],
                        "source_run_urls": [a["source_run_url"] for a in members if a.get("source_run_url")],
                        "independent_attempt_count": count, "identity_complete": complete,
                        "threshold": min_size, "status": status})
    decision = "eligible_for_batch_diagnosis" if any(c["status"] == "threshold_met_for_diagnosis" for c in cohorts) else "INCONCLUSIVE_NO_ELIGIBLE_COHORT_REACHES_MINIMUM"
    return {"minimum_comparable_attempts": min_size, "attempts": attempts, "cohorts": cohorts, "decision": decision,
            "counting_rule": "A and B from one workflow execution count as one independent attempt."}

def policy_for_cohort(cohort, *, targeted_fix_exists=False, regression_test_passed=False):
    if cohort.get("independent_attempt_count", 0) < cohort.get("threshold", MIN_COHORT_SIZE):
        return "INCONCLUSIVE_NEED_MORE_COMPARABLE_FAILURES"
    if not targeted_fix_exists:
        return "HOLD_NO_VERIFIED_TARGETED_FIX"
    if not regression_test_passed:
        return "HOLD_FIX_NOT_VERIFIED"
    return "RECOMMEND_BOUNDED_RERUN_MANUAL_APPROVAL_REQUIRED"

def discover_runs(base):
    for attempt_dir in sorted(Path(base).glob("qbatch-run-*-audit")):
        run_num = re.search(r"(\d{8,})", attempt_dir.name)
        attempt_id = attempt_dir.name.removesuffix("-audit")
        url = f"https://github.com/memoryprismv1/ael-runtime-accountability/actions/runs/{run_num.group(1)}" if run_num else None
        for run_root in sorted((attempt_dir / "runs").glob("run-*")):
            if (run_root / "manifest.json").exists():
                yield attempt_id, run_root, url

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Directory containing extracted qbatch-run-*-audit folders")
    parser.add_argument("--output", default="qbatch-cohort-report.json")
    parser.add_argument("--markdown", default="qbatch-cohort-report.md")
    args = parser.parse_args()
    records, errors = [], []
    for attempt_id, root, url in discover_runs(args.input):
        try:
            records.append(normalise(read_run(root, attempt_id), url))
        except Exception as exc:
            errors.append({"attempt_id": attempt_id, "run_path": str(root), "error": f"{type(exc).__name__}: {exc}"})
    cohort = analyse_cohorts(records)
    report = {"report_version": "0.3.0", "classification": "READ_ONLY_HISTORICAL_ANALYSIS_NOT_AUTOMATIC_RERUN_AUTHORITY",
              "raw_evidence_modified": False, "run_count": len(records),
              "attempt_count": len({r["attempt_id"] for r in records}),
              "integrity_pass_count": sum(r["integrity"]["status"] == "PASS" for r in records),
              "integrity_partial_count": sum(r["integrity"]["status"] == "PARTIAL" for r in records),
              "evidence_refs_rehashed": sum(r["integrity"]["evidence_refs_verified"] for r in records),
              "runs": records, "read_failures": errors, "cohort_analysis": cohort,
              "limitations": [
                  "Schema/logger labels were reused while capture capabilities evolved; recording profiles are inferred from observed events, not explicit producer IDs.",
                  "A missing event in an older profile is not proof that it did not occur.",
                  "A/B arms within one workflow attempt count as one independent attempt.",
                  "Historical manifests omit runner implementation revision and explicit capture-profile identity/worktree cleanliness; comparability is incomplete.",
                  "Failure signatures are observable symptoms, not proven root causes.",
                  "A rerun recommendation needs a targeted fix and passing regression test, and remains manual-approval-only."
              ]}
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Q-Batch historical cohort analysis", "",
             f"- Runs inspected: **{len(records)}**",
             f"- Independent workflow attempts: **{report['attempt_count']}**",
             f"- Fully verified runs (event chain, referenced artifacts and checksum): **{report['integrity_pass_count']} / {len(records)}**",
             f"- Partial-integrity runs (checksum absent): **{report['integrity_partial_count']}**",
             f"- Evidence references independently re-hashed: **{report['evidence_refs_rehashed']}**",
             f"- Decision: **{cohort['decision']}**", "", "## Run findings", "",
             "| Attempt | Condition | Recording profile | Failure signature | Evidence refs |",
             "|---|---|---|---|---:|"]
    for r in records:
        attempt = f"[{r['attempt_id']}]({r['source_run_url']})" if r.get("source_run_url") else r["attempt_id"]
        lines.append(f"| {attempt} | {r['condition_label']} | {r['format_profile']['profile']} | {r['failure']['signature']} | {r['integrity']['evidence_refs_verified']} |")
    lines += ["", "## Cohort results", "", "| Failure signature | Independent attempts | Result |", "|---|---:|---|"]
    for c in cohort["cohorts"]:
        lines.append(f"| {c['failure_signature']} | {c['independent_attempt_count']} | {c['status']} |")
    lines += ["", "No eligible cohort reaches the four-attempt threshold. Historical manifests also omit runner implementation revision and explicit capture-profile provenance, so comparability remains incomplete. No batch diagnosis or rerun recommendation is authorised.", "", "## Interpretation limits", ""]
    lines += [f"- {x}" for x in report["limitations"]]
    Path(args.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS" if records and not errors else "PARTIAL", "runs": len(records),
                      "attempts": report["attempt_count"], "integrity_pass": report["integrity_pass_count"],
                      "decision": cohort["decision"], "read_failures": len(errors)}, indent=2))
    return 0 if records and not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
