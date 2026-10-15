"""Explicit adapter registry; importing does not load GPU dependencies."""
import hashlib
import importlib
import sys
from pathlib import Path

from ..io import digest, jsonl
from .base import Adapter, InferenceError, Prediction, UnsupportedInput


def request_key(request, images):
    return digest({'request': request, 'images_sha256': [hashlib.sha256(b).hexdigest() for b in images]})


class Replay(Adapter):
    """Offline contract tests or private receipt reuse; never a new model measurement."""
    thread_safe = True

    def __init__(self, config):
        self.rows = {}
        for row in jsonl(config['receipts']):
            if row['request_key'] in self.rows:
                raise ValueError('Duplicate replay request')
            self.rows[row['request_key']] = row

    def predict(self, request, images):
        row = self.rows.get(request_key(request, images))
        if not row:
            raise UnsupportedInput('No matching offline receipt')
        return Prediction(row['answers'], row.get('refused', []), row.get('usage', {}), row.get('model'))


def create(config):
    if not isinstance(config.get('revision'), str) or not config['revision'].strip():
        raise ValueError('Record a model revision (or explicitly provider-unpinned)')
    if any(k in config for k in ('api_key', 'token', 'authorization', 'headers', 'password')):
        raise ValueError('Credentials belong in environment variables, not model configs')
    name = config['adapter']
    if name == 'replay':
        return Replay(config)
    if name in ('native_http', 'openai_decisions'):
        from .http import NativeHTTP, OpenAIDecisions
        return (OpenAIDecisions if name == 'openai_decisions' else NativeHTTP)(config)
    if name in ('kev', 'bosun', 'jev_sdk'):
        from .local import Kev, Bosun, JevSDK
        return {'kev': Kev, 'bosun': Bosun, 'jev_sdk': JevSDK}[name](config)
    if name == 'python':
        # Explicit local plugin chosen by the person running this command.
        # Never imported by the untrusted community-submission validator.
        if config.get('module_search_path'):
            path = str(Path(config['module_search_path']).resolve())
            if path not in sys.path:
                sys.path.insert(0, path)
        module, factory = config['factory'].split(':', 1)
        return getattr(importlib.import_module(module), factory)(config)
    raise ValueError('Unknown adapter')
