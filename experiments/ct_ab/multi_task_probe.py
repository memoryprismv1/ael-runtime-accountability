"""Paired multi-task CT skill probe.

Each task is sent to the same model once without and once with the pinned skill.
This captures observable behaviour and resource use; it does not infer hidden cognition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .agent_loop import OllamaClient, build_system_prompt
from .paired_runner import _git_blob_sha1, _skill_source_spec

PROBE_SYSTEM = (
    "You are answering a small evidence-interpretation question. Be concise and precise. "
    "Separate what the evidence establishes from what remains unknown. "
    "Do not write code or an implementation plan unless the user asks."
)
OPTIONS = {"temperature": 0, "num_predict": 500, "num_ctx": 4096}


def build_request(model: str, prompt: str, skill_text: str | None) -> dict[str, Any]:
    return {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": build_system_prompt(skill_text, PROBE_SYSTEM)},
            {"role": "user", "content": prompt},
        ],
        "options": dict(OPTIONS),
    }


def run_tasks(client: Any, model: str, skill_text: str, tasks: list[dict[str, Any]],
              output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "probe_id": "ct-multi-task-v1",
        "model": model,
        "options": OPTIONS,
        "task_count": len(tasks),
        "conditions": {},
        "interpretation_limits": [
            "One response per condition and task is exploratory; it does not establish general skill effectiveness.",
            "Captured skill delivery does not prove attention to or compliance with the skill.",
            "Token and duration metadata are operational measurements, not quality scores.",
            "Task scoring criteria are reference guidance; responses are not automatically scored."
        ]
    }
    for task in tasks:
        task_id = task["id"]
        report["conditions"][task_id] = {
            "category": task["category"],
            "prompt": task["prompt"],
            "scoring_criteria": task["scoring_criteria"],
            "responses": {}
        }
        for label, supplied_skill in (("skill_off", None), ("skill_on", skill_text)):
            request = build_request(model, task["prompt"], supplied_skill)
            request_bytes = json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
            request_path = output_dir / f"{task_id}-{label}-request.json"
            request_path.write_bytes(request_bytes)
            system = request["messages"][0]["content"]
            skill_present = (
                "=== CRITICAL THINKING SKILL (verbatim supplied file) ===" in system
                and skill_text in system
            )
            response = client.chat(request)
            response_bytes = json.dumps(response, ensure_ascii=False, sort_keys=True).encode("utf-8")
            response_path = output_dir / f"{task_id}-{label}-response.json"
            response_path.write_bytes(response_bytes)
            message = response.get("message", {})
            report["conditions"][task_id]["responses"][label] = {
                "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
                "user_prompt_sha256": hashlib.sha256(request["messages"][1]["content"].encode("utf-8")).hexdigest(),
                "model": request["model"],
                "options_sha256": hashlib.sha256(json.dumps(request["options"], sort_keys=True).encode("utf-8")).hexdigest(),
                "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
                "request_artifact": request_path.name,
                "response_artifact": response_path.name,
                "skill_in_system_message": skill_present,
                "response_text": message.get("content", ""),
                "finish_reason": response.get("done_reason"),
                "prompt_eval_count": response.get("prompt_eval_count"),
                "eval_count": response.get("eval_count"),
                "prompt_eval_duration_ns": response.get("prompt_eval_duration"),
                "eval_duration_ns": response.get("eval_duration"),
                "total_duration_ns": response.get("total_duration")
            }
    report["request_comparison"] = {
        "task_prompts_identical_between_conditions": all(
            report["conditions"][task["id"]]["responses"]["skill_off"]["user_prompt_sha256"]
            == report["conditions"][task["id"]]["responses"]["skill_on"]["user_prompt_sha256"]
            for task in tasks
        ),
        "model_and_options_identical_between_conditions": all(
            report["conditions"][task["id"]]["responses"]["skill_off"]["model"]
            == report["conditions"][task["id"]]["responses"]["skill_on"]["model"]
            and report["conditions"][task["id"]]["responses"]["skill_off"]["options_sha256"]
            == report["conditions"][task["id"]]["responses"]["skill_on"]["options_sha256"]
            for task in tasks
        ),
        "full_request_payloads_differ_between_conditions": all(
            report["conditions"][task["id"]]["responses"]["skill_off"]["request_sha256"]
            != report["conditions"][task["id"]]["responses"]["skill_on"]["request_sha256"]
            for task in tasks
        ),
        "skill_absent_in_all_controls": all(
            not report["conditions"][task["id"]]["responses"]["skill_off"]["skill_in_system_message"]
            for task in tasks
        ),
        "skill_present_in_all_treatments": all(
            report["conditions"][task["id"]]["responses"]["skill_on"]["skill_in_system_message"]
            for task in tasks
        )
    }
    (output_dir / "multi-task-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--tasks-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=360.0)
    args = parser.parse_args()

    spec = _skill_source_spec()
    skill_bytes = args.skill_path.read_bytes()
    actual_blob = _git_blob_sha1(skill_bytes)
    if actual_blob != spec["git_blob_sha1"]:
        raise SystemExit(
            f"Pinned skill mismatch: expected Git blob {spec['git_blob_sha1']}, got {actual_blob}"
        )
    tasks = json.loads(args.tasks_path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit("Task file must contain a non-empty JSON array")
    ids = [task.get("id") for task in tasks]
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise SystemExit("Each task must have a unique non-empty id")

    client = OllamaClient(args.base_url, timeout=args.timeout)
    info = client.info()
    available = client.list_models()
    if not any(str(item.get("name", "")).split(":")[0] == args.model.split(":")[0] for item in available):
        raise SystemExit(f"Configured model {args.model!r} is not present in Ollama: {available!r}")

    report = run_tasks(client, args.model, skill_bytes.decode("utf-8"), tasks, args.output)
    report["skill_source"] = {
        "repository": spec["repository"],
        "path": spec["path"],
        "commit": spec["commit"],
        "git_blob_sha1": actual_blob,
        "sha256": hashlib.sha256(skill_bytes).hexdigest()
    }
    report["ollama"] = info
    (args.output / "multi-task-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "probe_id": report["probe_id"],
        "task_count": len(tasks),
        "responses_expected": len(tasks) * 2,
        "skill_blob_verified": actual_blob == spec["git_blob_sha1"],
        "report": str(args.output / "multi-task-report.json")
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
