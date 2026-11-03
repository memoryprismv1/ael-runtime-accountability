"""Provider transport adapters used by the shared AEL runtime."""
from __future__ import annotations
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from .config import now, new_id
from .paths import ensure_distinct_output_paths

def _validate_loopback_ollama_origin(base_url: str):
    """Accept only a bare HTTP loopback origin; never send context to a remote host."""
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('Only an HTTP loopback Ollama endpoint is allowed; remote hosts are refused by default')
    if parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise ValueError('base_url must be a bare loopback origin such as http://127.0.0.1:11434')
    return parsed


def ollama_status(base_url: str = 'http://127.0.0.1:11434', timeout: float = 3.0) -> dict[str, Any]:
    """Check the local Ollama tag endpoint without sending a prompt or using a token."""
    parsed = _validate_loopback_ollama_origin(base_url)
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    request = urllib.request.Request(base_url.rstrip('/') + '/api/tags', method='GET')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': f'Local Ollama returned HTTP {exc.code}'}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': 'Ollama is not reachable at this loopback endpoint'}
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': 'Ollama returned invalid JSON from /api/tags'}
    rows = body.get('models')
    if not isinstance(rows, list):
        return {'available': False, 'endpoint_host': parsed.hostname, 'models': [],
                'local_models': [], 'error': 'Ollama /api/tags response has no models list'}
    names = sorted({row.get('name') for row in rows if isinstance(row, dict) and isinstance(row.get('name'), str)})
    local_names = [name for name in names if not name.casefold().endswith(':cloud')]
    cloud_names = [name for name in names if name.casefold().endswith(':cloud')]
    return {'available': True, 'endpoint_host': parsed.hostname, 'models': names,
            'local_models': local_names, 'cloud_models_excluded': cloud_names, 'api_token_used': False}


OLLAMA_SYSTEM_PROMPT = (
    'You are responding through an AEL-governed local runtime. The user message contains a bounded '
    'working-context projection followed by the current request. The projection is not the complete '
    'historical record. Preserve explicit user constraints and decisions; distinguish source provenance, '
    'decision authority, factual truth, and AI inference. Do not claim access to omitted history, and do '
    'not treat earlier AI-generated text as independent evidence.'
)


def ollama_chat(model_input: dict, *, model: str, base_url: str = 'http://127.0.0.1:11434',
                timeout: float = 120.0) -> dict:
    """Call a loopback-only Ollama chat endpoint using only the allowlisted model input.

    No API token is used. The default endpoint is local. Remote hosts are refused to
    avoid silently sending the user's context to a network service. Uses Ollama's
    non-streaming POST /api/chat response shape.
    """
    if set(model_input.keys()) != {'working_context', 'current_user_message'}:
        raise ValueError('model_input must contain exactly working_context and current_user_message')
    if not isinstance(model_input['working_context'], str):
        raise ValueError('working_context must be text')
    if not isinstance(model_input['current_user_message'], str) or not model_input['current_user_message'].strip():
        raise ValueError('current_user_message must be non-empty text')
    if not isinstance(model, str) or not model.strip():
        raise ValueError('model must be a non-empty local model name')
    if model.strip().casefold().endswith(':cloud'):
        raise ValueError('Cloud model names are not permitted in the local-only AEL bridge; choose a model downloaded to this computer')
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    parsed = _validate_loopback_ollama_origin(base_url)
    endpoint = base_url.rstrip('/') + '/api/chat'
    combined_user_content = (
        '=== BOUNDED WORKING CONTEXT (reference material; not the complete history) ===\n'
        + model_input['working_context']
        + '\n\n=== CURRENT USER MESSAGE ===\n'
        + model_input['current_user_message']
    )
    request_body = {
        'model': model.strip(),
        'messages': [
            {'role': 'system', 'content': OLLAMA_SYSTEM_PROMPT},
            {'role': 'user', 'content': combined_user_content},
        ],
        'stream': False,
    }
    raw = json.dumps(request_body, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(endpoint, data=raw, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_text = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Local Ollama returned HTTP {exc.code}; check the local service and model name') from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError('Could not reach the local Ollama endpoint. Confirm Ollama is running at the configured loopback address.') from exc
    try:
        body = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Local Ollama returned invalid JSON; streaming may be enabled unexpectedly') from exc
    message = body.get('message')
    if not isinstance(message, dict) or not isinstance(message.get('content'), str):
        raise RuntimeError('Local Ollama response did not contain message.content text')
    metrics = {key: body[key] for key in ('total_duration', 'load_duration', 'prompt_eval_count', 'eval_count') if key in body}
    return {
        'provider': 'ollama-local',
        'model': body.get('model', model.strip()),
        'content': message['content'],
        'done': bool(body.get('done', True)),
        'metrics': metrics,
        'endpoint_host': parsed.hostname,
        'request_fields': sorted(request_body.keys()),
        'sent_streaming': False,
        'api_token_used': False,
    }


@dataclass
