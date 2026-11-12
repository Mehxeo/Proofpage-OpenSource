import importlib.machinery
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from proofpage import offline_models


class OfflineModelTests(unittest.TestCase):
    def test_no_file_or_missing_runtime_fails_closed_without_endpoint_fallback(self):
        with patch.dict(os.environ, {'PROOFPAGE_OFFLINE_MODEL_FILE': ''}), patch('proofpage.offline_models.importlib.util.find_spec', return_value=None):
            self.assertFalse(offline_models.configuration()['configured'])
            with self.assertRaisesRegex(ValueError, 'local GGUF'):
                offline_models.complete_json([])
        with patch.dict(os.environ, {'PROOFPAGE_OFFLINE_MODEL_FILE': 'https://models.example/model.gguf'}):
            self.assertFalse(offline_models.configuration()['configured'])

    def test_in_process_runtime_gets_local_path_and_no_network_is_used(self):
        runtime = types.ModuleType('llama_cpp')
        runtime.__spec__ = importlib.machinery.ModuleSpec('llama_cpp', loader=None)
        model = Mock()
        model.create_chat_completion.return_value = {'choices': [{'message': {'content': json.dumps({'summary': 'Fictional local result'})}}]}
        runtime.Llama = Mock(return_value=model)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.gguf'
            path.write_bytes(b'GGUF')  # Simulated runtime fixture; not a real inference/model-quality test.
            with patch.dict(sys.modules, {'llama_cpp': runtime}), patch.dict(os.environ, {'PROOFPAGE_OFFLINE_MODEL_FILE': str(path)}), patch('socket.socket', side_effect=AssertionError('No network')), patch.object(offline_models, '_loaded', None), patch.object(offline_models, '_identity', None):
                self.assertEqual(offline_models.complete_json([{'role': 'user', 'content': 'Fictional document.'}]), {'summary': 'Fictional local result'})
                self.assertEqual(runtime.Llama.call_args.kwargs['model_path'], str(path.resolve()))
                self.assertEqual(runtime.Llama.call_args.kwargs['n_gpu_layers'], 0)
                self.assertNotIn('rpc_servers', runtime.Llama.call_args.kwargs)
                model.create_chat_completion.return_value = {'choices': [{'message': {'content': 'invalid JSON'}}]}
                with self.assertRaisesRegex(ValueError, 'No hosted fallback'):
                    offline_models.complete_json([])
