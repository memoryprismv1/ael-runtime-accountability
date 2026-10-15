import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runtime
import ael_chat


class LocalBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.captured = []

        outer = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != '/api/tags':
                    self.send_response(404); self.end_headers(); return
                body = json.dumps({'models': [
                    {'name': 'mock-local-model:latest', 'size': 123},
                    {'name': 'demo:cloud', 'size': 0},
                ]}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

            def do_POST(self):
                size = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(size).decode())
                outer.captured.append({'path': self.path, 'body': body})
                response = json.dumps({
                    'model': body.get('model', 'mock-local-model:latest'),
                    'message': {'role': 'assistant', 'content': 'mock AEL local answer'},
                    'done': True,
                    'prompt_eval_count': 12,
                    'eval_count': 5,
                }).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response))); self.end_headers(); self.wfile.write(response)

            def log_message(self, *args):
                return

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)
        self.tmp.cleanup()

    def test_default_data_dir_can_be_set_without_editing_code(self):
        chosen = self.root / "persistent-ael-data"
        with patch.dict(os.environ, {"AEL_RUNTIME_HOME": str(chosen)}):
            self.assertEqual(runtime.default_data_dir(), chosen)

    def test_status_lists_installed_local_models_and_excludes_cloud(self):
        result = runtime.ollama_status(self.endpoint, timeout=5)
        self.assertTrue(result['available'])
        self.assertEqual(result['local_models'], ['mock-local-model:latest'])
        self.assertEqual(result['cloud_models_excluded'], ['demo:cloud'])
        self.assertFalse(result['api_token_used'])

    def test_ollama_status_cli_returns_nonzero_when_service_is_unavailable_without_creating_db(self):
        import subprocess
        db_path = self.root / "must-not-be-created.sqlite3"
        completed = subprocess.run([
            sys.executable, str(ROOT / "runtime.py"), "--db", str(db_path), "ollama-status",
            "--endpoint", "http://127.0.0.1:1", "--timeout", "0.1",
        ], capture_output=True, text=True, timeout=5)
        self.assertEqual(completed.returncode, 2, msg=completed.stderr)
        self.assertFalse(db_path.exists())
        self.assertIn('available', completed.stdout)

    def test_status_refuses_remote_endpoint(self):
        with self.assertRaisesRegex(ValueError, 'loopback'):
            runtime.ollama_status('http://example.com:11434')

    def test_local_adapter_refuses_cloud_model_even_if_named(self):
        with self.assertRaisesRegex(ValueError, 'Cloud model names are not permitted'):
            runtime.ollama_chat({'working_context': 'ctx', 'current_user_message': 'hi'},
                                model='demo:cloud', base_url=self.endpoint, timeout=5)

    def test_interactive_shell_runs_turns_and_new_chat_isolation(self):
        db_path = self.root / 'data' / 'ael.sqlite3'
        audit_dir = self.root / 'audit'
        user_inputs = iter(['hello from chat one', '/new', 'hello from chat two', '/quit'])
        args = [
            '--db', str(db_path), '--account', 'test-account', '--project', 'test-project',
            '--chat', 'chat-one', '--endpoint', self.endpoint, '--timeout', '5',
            '--audit-dir', str(audit_dir),
        ]
        output = io.StringIO()
        with patch('builtins.input', side_effect=lambda _prompt='': next(user_inputs)), contextlib.redirect_stdout(output):
            code = ael_chat.main(args)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.captured), 2)
        self.assertTrue(all(item['path'] == '/api/chat' for item in self.captured))
        for item in self.captured:
            self.assertEqual(set(item['body']), {'model', 'messages', 'stream'})
            self.assertFalse(item['body']['stream'])
            self.assertNotIn('audit', json.dumps(item['body']).casefold())
            self.assertNotIn('event_seq', json.dumps(item['body']))
        self.assertIn('mock AEL local answer', output.getvalue())
        self.assertIn('New isolated chat:', output.getvalue())
        con = runtime.connect(db_path)
        try:
            chats = {r['chat_id'] for r in con.execute(
                "SELECT DISTINCT chat_id FROM events WHERE event_type IN ('user_request','assistant_turn')"
            ).fetchall()}
            self.assertEqual(len(chats), 2)
            user_messages = {r['content'] for r in con.execute(
                "SELECT content FROM events WHERE event_type='user_request'"
            ).fetchall()}
            self.assertEqual(user_messages, {'hello from chat one', 'hello from chat two'})
        finally:
            con.close()
        audit_files = list(audit_dir.rglob('*.json'))
        self.assertEqual(len(audit_files), 2)
        for path in audit_files:
            audit = json.loads(path.read_text(encoding='utf-8'))
            self.assertFalse(audit['api_token_used'])


if __name__ == '__main__':
    unittest.main()
