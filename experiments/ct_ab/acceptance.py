"""Independent acceptance runner for the Kanban clone.

This code lives outside the model's writable workspace and is run only after an
agent run completes. Its test source is not exposed by the agent tools.
"""
from __future__ import annotations
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

COLUMNS = [
    {"id": "todo", "title": "To Do"},
    {"id": "in_progress", "title": "In Progress"},
    {"id": "done", "title": "Done"},
]


class AppClient:
    def __init__(self, base_url: str, timeout: float = 2.0):
        self.base_url = base_url
        self.timeout = timeout

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, str, bytes]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status, response.headers.get("Content-Type", ""), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type", ""), exc.read()

    def json(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        status, content_type, raw = self.request(method, path, body)
        if not raw:
            return status, {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise AssertionError(f"{method} {path} did not return valid JSON (HTTP {status}, content-type {content_type})") from exc
        if not isinstance(parsed, dict):
            raise AssertionError(f"{method} {path} did not return a JSON object")
        return status, parsed


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start(workspace: Path, data_file: Path, log_file: Path, timeout: float = 12.0) -> tuple[subprocess.Popen[bytes], AppClient]:
    if not (workspace / "app.py").is_file():
        raise FileNotFoundError("required entry point app.py is missing")
    port = _free_port()
    allowed = {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","TMPDIR","PATHEXT","SYSTEMDRIVE","COMSPEC","LANG","LC_ALL"}
    env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
    env["BOARD_DATA_FILE"] = str(data_file)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    stream = log_file.open("wb")
    proc = subprocess.Popen(
        [sys.executable, "app.py", "--host", "127.0.0.1", "--port", str(port)],
        cwd=workspace,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=stream,
        stderr=subprocess.STDOUT,
    )
    proc._acceptance_stream = stream  # type: ignore[attr-defined]
    client = AppClient(f"http://127.0.0.1:{port}")
    until = time.monotonic() + timeout
    last_error = "server has not started"
    while time.monotonic() < until:
        if proc.poll() is not None:
            stream.flush()
            tail = log_file.read_text(encoding="utf-8", errors="replace")[-4000:] if log_file.exists() else ""
            _stop(proc)
            raise RuntimeError(f"application exited during startup (code {proc.returncode}): {tail}")
        try:
            status, _, _ = client.request("GET", "/")
            if status == 200:
                return proc, client
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.1)
    _stop(proc)
    tail = log_file.read_text(encoding="utf-8", errors="replace")[-4000:] if log_file.exists() else ""
    raise RuntimeError(f"server was not ready in {timeout}s: {last_error}\n{tail}")


def _stop(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    stream = getattr(proc, "_acceptance_stream", None)
    if stream:
        stream.flush()
        stream.close()


def _json_card(client: AppClient, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any], dict[str, Any] | None]:
    status, content, raw = client.request(method, path, body)
    if not raw:
        return status, {}, None
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise AssertionError(f"{method} {path} must return a JSON object")
    card = parsed.get("card") if isinstance(parsed.get("card"), dict) else None
    return status, parsed, card


def run_acceptance(workspace: str | Path, output_dir: str | Path, startup_timeout: float = 12.0) -> dict[str, Any]:
    ws = Path(workspace).resolve(strict=True)
    out = Path(output_dir).resolve()
    if not ws.is_dir():
        raise ValueError("workspace must be a directory")
    if out == ws or ws in out.parents or out in ws.parents:
        raise ValueError("acceptance output and agent workspace must be disjoint")
    out.mkdir(parents=True, exist_ok=True)
    data_file = out / "board-state.json"
    data_file.unlink(missing_ok=True)
    results: list[dict[str, Any]] = []
    proc: subprocess.Popen[bytes] | None = None
    client: AppClient | None = None
    log_paths = [out / "application-first.log", out / "application-restarted.log"]

    def check(name: str, fn: Callable[[], dict[str, Any] | None]) -> None:
        try:
            details = fn() or {}
            results.append({"name": name, "status": "PASS", "details": details})
        except Exception as exc:
            results.append({"name": name, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})

    try:
        proc, client = _start(ws, data_file, log_paths[0], startup_timeout)
        def homepage() -> dict[str, Any]:
            status, ctype, raw = client.request("GET", "/")
            html = raw.decode("utf-8", "replace")
            required = ['id="board"', 'id="create-card-form"', 'id="card-title"', 'id="card-description"', 'id="card-column"', 'data-action="create"', 'data-action="edit"', 'data-action="move"', 'data-action="delete"']
            missing = [item for item in required if item not in html]
            wiring = {
                "board_refresh": "fetch('/api/board')" in html or 'fetch("/api/board")' in html,
                "card_api": "fetch('/api/cards" in html or 'fetch("/api/cards' in html,
                "submit_handler": "addEventListener('submit'" in html or 'addEventListener("submit"' in html,
                "click_handler": "addEventListener('click'" in html or 'addEventListener("click"' in html,
                "move_route": "/move" in html,
                "delete_method": "method:'DELETE'" in html or 'method:"DELETE"' in html or "method: 'DELETE'" in html or 'method: "DELETE"' in html,
                "patch_method": "method:'PATCH'" in html or 'method:"PATCH"' in html or "method: 'PATCH'" in html or 'method: "PATCH"' in html,
            }
            if status != 200 or "text/html" not in ctype.lower() or missing or not all(wiring.values()):
                raise AssertionError(f"HTTP={status}, content-type={ctype}, missing required UI hooks: {missing}, wiring: {wiring}")
            return {"status_code": status, "content_type": ctype, "required_ui_hooks": len(required), "static_ui_wiring": wiring}
        check("homepage_and_automation_hooks", homepage)

        def board_shape() -> dict[str, Any]:
            status, doc = client.json("GET", "/api/board")
            columns = doc.get("columns")
            if status != 200 or not isinstance(columns, list):
                raise AssertionError(f"expected 200 and columns array, got HTTP {status}")
            summary = [{"id": c.get("id"), "title": c.get("title"), "cards_is_array": isinstance(c.get("cards"), list)} for c in columns if isinstance(c, dict)]
            if [(x.get("id"), x.get("title")) for x in columns if isinstance(x, dict)] != [(x["id"], x["title"]) for x in COLUMNS]:
                raise AssertionError(f"column contract mismatch: {summary}")
            if not all(isinstance(c.get("cards"), list) for c in columns):
                raise AssertionError("each column must have a cards array")
            return {"columns": summary}
        check("initial_board_contract", board_shape)

        def invalid_title() -> dict[str, Any]:
            status, doc = client.json("POST", "/api/cards", {"title": "   ", "description": "invalid"})
            if status != 400:
                raise AssertionError(f"whitespace title must return 400, got {status}: {doc}")
            status2, doc2 = client.json("POST", "/api/cards", {"title": "Valid", "column_id": "unknown"})
            if status2 != 400:
                raise AssertionError(f"unknown column must return 400, got {status2}: {doc2}")
            return {"empty_title_status": status, "unknown_column_status": status2}
        check("input_validation", invalid_title)

        card_id_holder: dict[str, str] = {}
        def card_lifecycle() -> dict[str, Any]:
            status, _, card = _json_card(client, "POST", "/api/cards", {"title": "First card", "description": "initial body", "column_id": "todo"})
            if status != 201 or not card:
                raise AssertionError(f"create must return 201 with card object, got {status}, {card}")
            card_id = str(card.get("id", ""))
            if not card_id or card.get("title") != "First card" or card.get("description") != "initial body" or card.get("column_id") != "todo":
                raise AssertionError(f"created card fields invalid: {card}")
            card_id_holder["id"] = card_id
            status, _, edited = _json_card(client, "PATCH", f"/api/cards/{card_id}", {"title": "Edited card", "description": "edited body"})
            if status != 200 or not edited or edited.get("title") != "Edited card" or edited.get("description") != "edited body":
                raise AssertionError(f"edit failed: HTTP {status}, card={edited}")
            status, _, moved = _json_card(client, "POST", f"/api/cards/{card_id}/move", {"column_id": "in_progress"})
            if status != 200 or not moved or moved.get("column_id") != "in_progress":
                raise AssertionError(f"move failed: HTTP {status}, card={moved}")
            status, doc = client.json("GET", "/api/board")
            placements = [(c.get("id"), card.get("id")) for c in doc.get("columns", []) if isinstance(c, dict) for card in c.get("cards", []) if isinstance(card, dict)]
            if ("in_progress", card_id) not in placements:
                raise AssertionError(f"moved card is not in In Progress: {placements}")
            status, _, _ = _json_card(client, "DELETE", f"/api/cards/{card_id}")
            if status != 204:
                raise AssertionError(f"delete must return 204, got {status}")
            status, doc = client.json("GET", "/api/board")
            remaining = [card for col in doc.get("columns", []) if isinstance(col, dict) for card in col.get("cards", []) if isinstance(card, dict)]
            if any(str(card.get("id")) == card_id for card in remaining):
                raise AssertionError("deleted card still appears on board")
            return {"card_id": card_id, "create": 201, "edit": 200, "move": 200, "delete": 204}
        check("create_edit_move_delete", card_lifecycle)

        def not_found() -> dict[str, Any]:
            status, doc = client.json("PATCH", "/api/cards/__missing_card__", {"title": "No"})
            if status != 404:
                raise AssertionError(f"editing unknown card must return 404, got {status}: {doc}")
            status, doc = client.json("POST", "/api/cards/__missing_card__/move", {"column_id": "done"})
            if status != 404:
                raise AssertionError(f"moving unknown card must return 404, got {status}: {doc}")
            return {"unknown_edit_status": 404, "unknown_move_status": 404}
        check("missing_card_handling", not_found)

        persist_id: dict[str, str] = {}
        def persistence_create() -> dict[str, Any]:
            status, _, card = _json_card(client, "POST", "/api/cards", {"title": "Survives restart", "description": "persistent payload", "column_id": "done"})
            if status != 201 or not card or not str(card.get("id", "")):
                raise AssertionError(f"persistence fixture create failed: HTTP {status}, card={card}")
            persist_id["id"] = str(card["id"])
            if not data_file.is_file():
                raise AssertionError("BOARD_DATA_FILE was not created at the requested path")
            return {"card_id": persist_id["id"], "data_file_exists": True}
        check("persistence_write", persistence_create)
        _stop(proc)
        proc = None
        try:
            proc, client = _start(ws, data_file, log_paths[1], startup_timeout)
            def persistence_read() -> dict[str, Any]:
                status, doc = client.json("GET", "/api/board")
                cards = [card for col in doc.get("columns", []) if isinstance(col, dict) for card in col.get("cards", []) if isinstance(card, dict)]
                found = [card for card in cards if str(card.get("id")) == persist_id.get("id")]
                if status != 200 or len(found) != 1 or found[0].get("title") != "Survives restart" or found[0].get("description") != "persistent payload" or found[0].get("column_id") != "done":
                    raise AssertionError(f"card did not survive restart: HTTP {status}, matching cards={found}")
                return {"card_id": persist_id["id"], "survived_restart": True}
            check("persistence_across_restart", persistence_read)
        except Exception as exc:
            results.append({"name": "persistence_across_restart", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
    except Exception as exc:
        results.append({"name": "server_startup", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
        tail = (log_paths[0].read_text(encoding="utf-8", errors="replace")[-4000:] if log_paths[0].exists() else "")
        results.append({"name": "startup_diagnostics", "status": "INFO", "details": {"tail": tail}})
    finally:
        if proc is not None:
            _stop(proc)

    passed = sum(r["status"] == "PASS" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)
    report = {
        "acceptance_version": "1.0",
        "purpose": "Independent, post-run software acceptance; not an assessment of hidden reasoning.",
        "workspace_name": ws.name,
        "status": "PASS" if failed == 0 and passed >= 7 else "FAIL",
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
        "checks": results,
        "application_logs": [p.name for p in log_paths if p.exists()],
    }
    (out / "acceptance-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run_acceptance(args.workspace, args.output)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
