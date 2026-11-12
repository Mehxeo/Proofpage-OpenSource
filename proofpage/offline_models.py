"""Optional in-process GGUF inference. No model downloads or HTTP fallback."""
import importlib.util
import json
import os
import threading
from pathlib import Path

_LOCK = threading.RLock()
_loaded = None
_identity = None


def configuration():
    filename = os.environ.get('PROOFPAGE_OFFLINE_MODEL_FILE', '').strip()
    installed = importlib.util.find_spec('llama_cpp') is not None
    detail = ('Google Docs AI requires a local GGUF file and the optional offline-ai extra. '
              'Set PROOFPAGE_OFFLINE_MODEL_FILE to that file. No endpoint, cloud proxy, '
              'download, or hosted fallback is used. Reading Docs needs no model.')
    if not filename:
        return {'configured': False, 'installed': installed, 'detail': detail}
    path = Path(filename).expanduser()
    if not path.is_absolute() or path.suffix.lower() != '.gguf' or not path.is_file():
        return {'configured': False, 'installed': installed,
                'detail': 'Choose an existing local .gguf file using an absolute PROOFPAGE_OFFLINE_MODEL_FILE path.'}
    return {'configured': installed, 'installed': installed, 'model': path.name,
            'detail': 'Runs inside Proofpage using your local GGUF file. No data is sent to a model provider.' if installed else detail}


def complete_json(messages):
    global _loaded, _identity
    config = configuration()
    if not config['configured']:
        raise ValueError(config['detail'])
    from llama_cpp import Llama
    path = Path(os.environ['PROOFPAGE_OFFLINE_MODEL_FILE']).expanduser().resolve(strict=True)
    identity = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    with _LOCK:
        if identity != _identity:
            if _loaded is not None:
                _loaded.close()
            _loaded, _identity = None, None
            # CPU-only, no RPC backend, remote tokenizer, URL, or from_pretrained.
            _loaded = Llama(model_path=str(path), n_ctx=8192, n_gpu_layers=0,
                            n_threads=max(1, min(8, os.cpu_count() or 1)), verbose=False)
            _identity = identity
        try:
            response = _loaded.create_chat_completion(messages=messages, temperature=0,
                max_tokens=1800, response_format={'type': 'json_object'}, stream=False)
            result = json.loads(response['choices'][0]['message']['content'])
            if not isinstance(result, dict):
                raise ValueError('Expected a JSON object.')
            return result
        except (ValueError, KeyError, IndexError, TypeError):
            raise ValueError('The offline model could not return valid JSON within its context window. Use a smaller passage or another local GGUF model. No hosted fallback was attempted.') from None
