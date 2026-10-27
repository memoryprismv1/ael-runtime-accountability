"""Tiny, low-level CT skill delivery and behaviour probe.

Sends the same one-question prompt to the configured Ollama model twice:
once with the pinned CT skill in the system message and once without it.
Persists exact outgoing request bodies before transport and raw responses after.
This is a diagnostic probe, not a general capability benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .agent_loop import OllamaClient, build_system_prompt, skill_obj_fingerprint
from .paired_runner import _git_blob_sha1, _skill_source_spec

PROBE_ID = "sales-mismatch-v1"
PROMPT = (
    "A shop report says revenue rose 20% while transaction count fell 10%. "
    "Explain what follows from these figures and what cannot be concluded."
)
PROBE_SYSTEM = ("Answer in at most 3 short bullets and no more than 80 words total. "
                "Lead with the key conclusion. Separate what the figures imply from what remains unknown. "
                "Do not repeat the question, speculate about causes, or write code/an implementation plan unless asked.")
OPTIONS = {"temperature": 0, "num_predict": 180, "num_ctx": 4096}


def build_probe_request(model: str, skill_obj: Mapping[str, str] | None) -> dict[str, Any]:
    """Build a tiny request using the same system-prompt builder as production."""
    return {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": build_system_prompt(skill_obj, PROBE_SYSTEM)},
            {"role": "user", "content": PROMPT},
        ],
        "options": dict(OPTIONS),
    }


def run_probe(client: Any, model: str, skill_obj: Mapping[str, str], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    conditions = {"skill_off": None, "skill_on": dict(skill_obj)}
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "probe_id": PROBE_ID,
        "task_prompt": PROMPT,
        "model": model,
        "transport": "Ollama /api/chat via loopback client",
        "conditions": {},
        "interpretation_limits": [
            "A captured outgoing request proves the harness sent the skill object to the model transport, not that the model attended to or followed it.",
            "One prompt and one response per condition are diagnostic only; they do not establish general skill effectiveness.",
            "This probe tests mismatch interpretation and evidence calibration, not web research or website-building ability.",
        ],
    }
    for label, supplied_skill in conditions.items():
        request = build_probe_request(model, supplied_skill)
        request_bytes = json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
        request_path = output_dir / f"{label}-request.json"
        request_path.write_bytes(request_bytes)
        system = request["messages"][0]["content"]
        skill_present = bool(supplied_skill) and all(
            f"=== SKILL: {name} (verbatim supplied file) ===" in system and text in system
            for name, text in supplied_skill.items()
        )
        response = client.chat(request)
        response_bytes = json.dumps(response, ensure_ascii=False, sort_keys=True).encode("utf-8")
        response_path = output_dir / f"{label}-response.json"
        response_path.write_bytes(response_bytes)
        message = response.get("message", {})
        result["conditions"][label] = {
            "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
            "request_artifact": request_path.name,
            "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "response_artifact": response_path.name,
            "skill_in_system_message": skill_present,
            "skill_sha256": hashlib.sha256(supplied_skill["critical-thinking"].encode("utf-8")).hexdigest() if supplied_skill and "critical-thinking" in supplied_skill else None,
            "skill_obj_sha256": skill_obj_fingerprint(supplied_skill),
            "skill_hashes": {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in sorted(supplied_skill.items())} if supplied_skill else {},
            "response_text": message.get("content", ""),
            "finish_reason": response.get("done_reason"),
        }
    result["request_comparison"] = {
        "user_prompt_identical": all(
            json.loads((output_dir / f"{label}-request.json").read_text(encoding="utf-8"))["messages"][1]["content"] == PROMPT
            for label in conditions
        ),
        "skill_off_contains_skill": result["conditions"]["skill_off"]["skill_in_system_message"],
        "skill_on_contains_skill": result["conditions"]["skill_on"]["skill_in_system_message"],
    }
    result_path = output_dir / "probe-report.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    spec = _skill_source_spec()
    skill_bytes = args.skill_path.read_bytes()
    actual_blob = _git_blob_sha1(skill_bytes)
    if actual_blob != spec["git_blob_sha1"]:
        raise SystemExit(
            f"Pinned skill mismatch: expected Git blob {spec['git_blob_sha1']}, got {actual_blob}"
        )
    skill_obj = {"critical-thinking": skill_bytes.decode("utf-8")}
    client = OllamaClient(args.base_url, timeout=args.timeout)
    info = client.info()
    available = client.list_models()
    if not any(str(item.get("name", "")).split(":")[0] == args.model.split(":")[0] for item in available):
        raise SystemExit(f"Configured model {args.model!r} is not present in Ollama: {available!r}")

    report = run_probe(client, args.model, skill_obj, args.output)
    report["skill_source"] = {
        "repository": spec["repository"],
        "path": spec["path"],
        "commit": spec["commit"],
        "git_blob_sha1": actual_blob,
        "sha256": hashlib.sha256(skill_bytes).hexdigest(),
    }
    report["ollama"] = info
    report["request_comparison"]["transport_completed_for_both"] = all(
        (args.output / f"{label}-response.json").is_file() for label in ("skill_off", "skill_on")
    )
    (args.output / "probe-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "probe_id": PROBE_ID,
        "skill_blob_verified": actual_blob == spec["git_blob_sha1"],
        "skill_off_request_captured": (args.output / "skill_off-request.json").is_file(),
        "skill_on_request_captured": (args.output / "skill_on-request.json").is_file(),
        "report": str(args.output / "probe-report.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
