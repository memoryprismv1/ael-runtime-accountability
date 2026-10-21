"""A shared append-only JSONL event recorder for paired agent runs.

The logger must write outside the agent's project workspace. It intentionally
records observable tool/environment events and agent-declared summaries, not
hidden chain-of-thought.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "1.0"
LOGGER_VERSION = "0.1.0"
ZERO_HASH = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class RunLogger:
    """Single-writer event stream plus evidence/artifact capture."""

    def __init__(self, run_dir: str | Path, workspace_root: str | Path, manifest: Mapping[str, Any]):
        self.workspace = Path(workspace_root).resolve(strict=True)
        self.run_dir = Path(run_dir).resolve()
        if not self.workspace.is_dir():
            raise ValueError("workspace_root must be an existing directory")
        if self.run_dir == self.workspace or _is_within(self.run_dir, self.workspace) or _is_within(self.workspace, self.run_dir):
            raise ValueError("experiment run directory and agent workspace must be disjoint; logs may not live in the agent workspace")
        if self.run_dir.exists() and any(self.run_dir.iterdir()):
            raise FileExistsError(f"run directory must be new or empty: {self.run_dir}")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir = self.run_dir / "artifacts"
        self.artifact_dir.mkdir()
        self.events_path = self.run_dir / "events.jsonl"
        self._events = self.events_path.open("x", encoding="utf-8", newline="\n")
        self.run_id = str(manifest.get("run_id", ""))
        if not self.run_id:
            self._events.close()
            raise ValueError("manifest must have a non-empty run_id")
        self._seq = 0
        self._prev_hash: str | None = ZERO_HASH
        self._artifact_counter = 0
        required_manifest = {"run_id", "condition_label", "task_brief_sha256", "condition_config_sha256", "logger_version", "schema_version", "started_at_utc", "model", "environment", "resource_limits", "base_commit"}
        missing = required_manifest - set(manifest)
        if missing:
            self._events.close()
            raise ValueError(f"manifest missing fields: {sorted(missing)}")
        if manifest["condition_label"] not in {"A", "B", "REHEARSAL-A", "REHEARSAL-B"}:
            self._events.close()
            raise ValueError("condition_label must be blinded A/B or explicit rehearsal label")
        stored_manifest = dict(manifest)
        stored_manifest["written_at_utc"] = utc_now()
        stored_manifest["workspace"] = self.workspace.name
        (self.run_dir / "manifest.json").write_text(json.dumps(stored_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.emit("run_started", "runner", "setup", "succeeded", {"logger_version": LOGGER_VERSION, "schema_version": SCHEMA_VERSION})

    def emit(self, event_type: str, actor: str, phase: str, status: str, payload: Mapping[str, Any] | None = None, evidence_refs: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
        event: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "seq": self._seq + 1,
            "timestamp_utc": utc_now(),
            "phase": phase,
            "actor": actor,
            "event_type": event_type,
            "status": status,
            "payload": dict(payload or {}),
            "evidence_refs": [dict(item) for item in evidence_refs],
            "prev_event_sha256": self._prev_hash,
        }
        event_hash = sha256_bytes(canonical_json(event))
        event["event_sha256"] = event_hash
        self._events.write(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        self._events.flush()
        os.fsync(self._events.fileno())
        self._seq += 1
        self._prev_hash = event_hash
        return event

    def capture_artifact(self, name: str, content: bytes | str, media_type: str = "application/octet-stream") -> dict[str, Any]:
        """Save evidence in the runner-owned run directory and return its reference."""
        safe_name = Path(name).name
        if not safe_name or safe_name in {".", ".."} or safe_name != name or "/" in name or "\\" in name:
            raise ValueError("artifact name must be a plain filename without path separators")
        raw = content.encode("utf-8") if isinstance(content, str) else content
        self._artifact_counter += 1
        target = self.artifact_dir / f"{self._artifact_counter:04d}-{safe_name}"
        with target.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        ref = {"path": target.relative_to(self.run_dir).as_posix(), "sha256": sha256_bytes(raw), "size_bytes": len(raw)}
        self.emit("artifact_captured", "logger", "setup", "succeeded", {"media_type": media_type}, [ref])
        return ref

    def record_agent_plan(self, plan: str) -> dict[str, Any]:
        ref = self.capture_artifact("submitted-plan.md", plan, "text/markdown")
        return self.emit("plan_submitted", "agent", "planning", "declared", {"evidence_kind": "agent_declared", "note": "This is the submitted plan, not proof of actions taken."}, [ref])

    def record_agent_note(self, note: str, phase: str, category: str = "decision") -> dict[str, Any]:
        ref = self.capture_artifact(f"agent-note-{self._seq + 1}.txt", note, "text/plain")
        return self.emit("agent_note", "agent", phase, "declared", {"evidence_kind": "agent_declared", "category": category}, [ref])

    def run_command(self, command: Sequence[str], cwd: str | Path, phase: str, timeout_seconds: float = 120.0, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run a command and preserve stdout/stderr as hashed artifacts."""
        working_dir = Path(cwd).resolve(strict=True)
        if not _is_within(working_dir, self.workspace):
            raise ValueError("commands must run in or below the declared workspace")
        cmd = [str(part) for part in command]
        before = self.snapshot_workspace()
        self.emit("command_started", "runner", phase, "started", {"command": cmd, "cwd_relative": working_dir.relative_to(self.workspace).as_posix() or ".", "timeout_seconds": timeout_seconds})
        began = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=working_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, env=dict(env) if env else None, check=False)
            out = self.capture_artifact(f"command-{self._seq + 1}-stdout.txt", proc.stdout, "text/plain; charset=utf-8")
            err = self.capture_artifact(f"command-{self._seq + 1}-stderr.txt", proc.stderr, "text/plain; charset=utf-8")
            duration_ms = round((time.monotonic() - began) * 1000, 3)
            status = "succeeded" if proc.returncode == 0 else "failed"
            self.emit("command_finished", "runtime", phase, status, {"command": cmd, "exit_code": proc.returncode, "duration_ms": duration_ms}, [out, err])
            self.record_file_changes(before, self.snapshot_workspace())
            return proc
        except subprocess.TimeoutExpired as exc:
            duration_ms = round((time.monotonic() - began) * 1000, 3)
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            out = self.capture_artifact(f"command-timeout-{self._seq + 1}-stdout.txt", stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout, "text/plain; charset=utf-8")
            err = self.capture_artifact(f"command-timeout-{self._seq + 1}-stderr.txt", stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else stderr, "text/plain; charset=utf-8")
            self.emit("command_finished", "runtime", phase, "failed", {"command": cmd, "timeout": True, "timeout_seconds": timeout_seconds, "duration_ms": duration_ms}, [out, err])
            self.record_file_changes(before, self.snapshot_workspace())
            raise
        except OSError as exc:
            duration_ms = round((time.monotonic() - began) * 1000, 3)
            err = self.capture_artifact(f"command-launch-error-{self._seq + 1}.txt", f"{type(exc).__name__}: {exc}\n", "text/plain; charset=utf-8")
            self.emit("command_finished", "runtime", phase, "failed", {"command": cmd, "launch_error": type(exc).__name__, "duration_ms": duration_ms}, [err])
            self.emit("error", "runtime", phase, "observed", {"kind": "command_launch_error", "error_type": type(exc).__name__})
            self.record_file_changes(before, self.snapshot_workspace())
            raise

    def record_tool_call(self, tool_name: str, call_id: str, arguments: Mapping[str, Any], outcome: Mapping[str, Any], status: str = "succeeded", phase: str = "implementation") -> dict[str, Any]:
        """Record an orchestrated tool invocation and its returned result.

        Call this from the runner's tool-dispatch boundary. Merely relying on an
        agent to report its own tool use is not equivalent to observed logging.
        """
        if not tool_name or not call_id:
            raise ValueError("tool_name and call_id are required")
        if status not in {"succeeded", "failed", "skipped"}:
            raise ValueError("invalid tool-call status")
        input_ref = self.capture_artifact(f"tool-{call_id}-input.json", json.dumps(dict(arguments), ensure_ascii=False, indent=2, sort_keys=True), "application/json")
        output_ref = self.capture_artifact(f"tool-{call_id}-output.json", json.dumps(dict(outcome), ensure_ascii=False, indent=2, sort_keys=True, default=str), "application/json")
        return self.emit("tool_call", "runner", phase, status, {"tool_name": tool_name, "call_id": call_id}, [input_ref, output_ref])

    def record_model_exchange(self, request_metadata: Mapping[str, Any], prompt: str, response: str, usage: Mapping[str, Any] | None = None, phase: str = "implementation") -> dict[str, Any]:
        """Store exact supplied request/response text and provider metadata as artifacts.

        This is a capture API for a runner that controls the model transport; it
        cannot observe model requests made outside that transport.
        """
        metadata = dict(request_metadata)
        if not metadata.get("provider") or not metadata.get("model_id") or not metadata.get("request_id"):
            raise ValueError("request_metadata must include provider, model_id, and request_id")
        prompt_ref = self.capture_artifact(f"model-request-{metadata['request_id']}.txt", prompt, "text/plain; charset=utf-8")
        self.emit("model_request", "runner", phase, "observed", {"request_id": metadata["request_id"], "provider": metadata["provider"], "model_id": metadata["model_id"], "system_fingerprint": metadata.get("system_fingerprint"), "condition_config_sha256": metadata.get("condition_config_sha256")}, [prompt_ref])
        response_ref = self.capture_artifact(f"model-response-{metadata['request_id']}.txt", response, "text/plain; charset=utf-8")
        payload: dict[str, Any] = {"request_id": metadata["request_id"], "provider": metadata["provider"], "model_id": metadata["model_id"], "latency_ms": metadata.get("latency_ms"), "finish_reason": metadata.get("finish_reason"), "usage": dict(usage or {})}
        return self.emit("model_response", "runtime", phase, "observed", payload, [response_ref])

    def record_requirement_check(self, requirement_id: str, result: str, evidence_refs: Iterable[Mapping[str, Any]] = (), note: str | None = None) -> dict[str, Any]:
        if result not in {"pass", "fail", "blocked", "not_tested"}:
            raise ValueError("requirement result must be pass/fail/blocked/not_tested")
        payload: dict[str, Any] = {"requirement_id": requirement_id, "result": result}
        if note:
            payload["note"] = note
        return self.emit("requirement_check", "reviewer", "verification", "succeeded" if result == "pass" else "failed" if result == "fail" else "observed", payload, evidence_refs)

    def record_commit(self, commit_sha: str, message: str, branch: str, changed_paths: Sequence[str]) -> dict[str, Any]:
        if len(commit_sha) < 7 or not branch or not message:
            raise ValueError("commit SHA, message, and branch are required")
        return self.emit("commit_created", "runtime", "delivery", "observed", {"commit_sha": commit_sha, "message": message, "branch": branch, "changed_paths": list(changed_paths)})

    def record_test_result(self, command: Sequence[str], exit_code: int, passed: int | None, failed: int | None, artifact_refs: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
        status = "succeeded" if exit_code == 0 and (failed in (None, 0)) else "failed"
        return self.emit("test_result", "runtime", "verification", status, {"command": list(command), "exit_code": exit_code, "passed": passed, "failed": failed}, artifact_refs)

    def snapshot_workspace(self) -> dict[str, str]:
        ignored_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__"}
        snapshot: dict[str, str] = {}
        for p in sorted(self.workspace.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(self.workspace)
            if any(part in ignored_dirs for part in rel.parts):
                continue
            snapshot[rel.as_posix()] = sha256_file(p)
        return snapshot

    def record_file_changes(self, before: Mapping[str, str], after: Mapping[str, str]) -> list[dict[str, Any]]:
        events = []
        for name in sorted(set(before) | set(after)):
            old, new = before.get(name), after.get(name)
            if old == new:
                continue
            action = "created" if old is None else "deleted" if new is None else "modified"
            events.append(self.emit("file_changed", "runner", "implementation", "observed", {"path": name, "action": action, "before_sha256": old, "after_sha256": new}))
        return events

    def finish(self, status: str = "succeeded", notes: str | None = None) -> None:
        if status not in {"succeeded", "failed", "skipped"}:
            raise ValueError("invalid run completion status")
        payload: dict[str, Any] = {"events_before_finish": self._seq, "completion_status": status}
        if notes:
            payload["notes"] = notes
        self.emit("run_finished", "runner", "delivery", status, payload)
        self._events.close()
        digest = sha256_file(self.events_path)
        (self.run_dir / "checksums.sha256").write_text(f"{digest}  events.jsonl\n", encoding="ascii")

    def close(self) -> None:
        if not self._events.closed:
            self._events.close()
