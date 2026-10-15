"""Native JSON and OpenAI Decisions transports. Credentials are environment-only."""
import base64
import copy
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from ..io import loads
from .base import Adapter, InferenceError, Prediction, UnsupportedInput


def data_url(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif raw.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        mime = 'image/webp'
    else:
        raise UnsupportedInput('Unsupported image encoding')
    return 'data:' + mime + ';base64,' + base64.b64encode(raw).decode()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class NativeHTTP(Adapter):
    thread_safe = True

    def __init__(self, config):
        self.config = config
        self.endpoint = config.get('endpoint') or os.environ.get(config.get('endpoint_env', ''), '')
        u = urllib.parse.urlsplit(self.endpoint)
        if u.username or u.password or u.query or u.fragment or not u.hostname:
            raise ValueError('Use an endpoint without embedded credentials or query strings')
        if u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('Use HTTPS, or HTTP on localhost for a local model server')
        key_env = config.get('api_key_env')
        self.key = os.environ.get(key_env, '') if key_env else ''
        if key_env and not self.key:
            raise ValueError('Required API credential environment variable is unset')

    def payload(self, request, images):
        payload = copy.deepcopy(request)
        if self.config.get('model'):
            payload['model'] = self.config['model']
        if images:
            if self.config.get('image_transport') != 'data_url':
                raise UnsupportedInput('This native endpoint has no configured image transport')
            payload['images'] = [data_url(image) for image in images]
        return payload

    def normalize(self, request, raw):
        if not isinstance(raw, dict) or not isinstance(raw.get('answers'), dict):
            raise InferenceError('invalid_response')
        if set(raw['answers']) != set(request['questions']):
            raise InferenceError('question_id_mismatch')
        refused = [k for k, v in raw['answers'].items() if isinstance(v, dict) and v.get('type') == 'refusal']
        return Prediction(raw['answers'], refused, raw.get('usage', {}), raw.get('model'))

    def predict(self, request, images):
        payload = self.payload(request, images)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if self.key:
            headers[self.config.get('auth_header', 'Authorization')] = self.config.get('auth_prefix', 'Bearer ') + self.key
        req = urllib.request.Request(self.endpoint, data=json.dumps(payload, ensure_ascii=False,
            allow_nan=False).encode(), headers=headers, method='POST')
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=self.config.get('timeout', 120)) as response:
                raw = response.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024:
                raise InferenceError('response_too_large')
            # Remove accidental key echoes before any decoded field can reach a receipt.
            text = raw.decode('utf-8')
            if self.key:
                text = text.replace(self.key, '[REDACTED]')
            return self.normalize(request, loads(text))
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get('Retry-After', '')
            retry_after = float(retry_after) if retry_after.isdigit() else None
            code = exc.code
            exc.close()
            # Never persist response bodies, headers, or exception URLs containing secrets.
            raise InferenceError(f'http_{code}', code in (408, 429) or 500 <= code < 600, retry_after) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            raise InferenceError('network_error', retryable=True) from None
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            raise InferenceError('invalid_response') from None


class OpenAIDecisions(NativeHTTP):
    def payload(self, request, images):
        if set(request) - {'state', 'questions', 'images', 'model'}:
            raise UnsupportedInput('Unmapped top-level native request fields')
        questions = []
        for name, q in request['questions'].items():
            if set(q) - {'type', 'instructions', 'criteria'}:
                raise UnsupportedInput('Unmapped native question fields')
            kind, instructions = q['type'], q['instructions']
            item = {'name': name, 'type': kind, 'instructions': instructions}
            if kind == 'choice':
                item['choices'] = [dict(value=k, **({'description': v} if v is not None else {}))
                                   for k, v in q['criteria'].items()]
            elif kind == 'score':
                item['levels'] = [{'label': v} for v in q['criteria']]
            elif kind == 'noul':
                item['type'] = 'predicate'
                if q.get('criteria'):
                    item['instructions'] += '\n\nCriteria (verbatim from the source question):\n' + json.dumps(q['criteria'], ensure_ascii=False, indent=2)
            else:
                raise UnsupportedInput('Unknown question type')
            questions.append(item)
        text = json.dumps(request['state'], ensure_ascii=False, indent=2, allow_nan=False)
        value = text
        if images:
            content = [{'type': 'input_text', 'text': text}]
            content += [{'type': 'input_image', 'image_url': data_url(image)} for image in images]
            value = [{'role': 'user', 'content': content}]
        return {'model': self.config['model'], 'input': value, 'questions': questions}

    def normalize(self, request, raw):
        entries = raw['answers']
        if len(entries) != len(request['questions']) or {a['name'] for a in entries} != set(request['questions']):
            raise InferenceError('question_id_mismatch')
        answers, refused = {}, []
        for a in entries:
            name, kind = a['name'], request['questions'][a['name']]['type']
            if a['type'] == 'refusal':
                refused.append(name)
                continue
            expected_type = 'predicate' if kind == 'noul' else kind
            if a['type'] != expected_type:
                raise InferenceError('answer_type_mismatch')
            if kind == 'noul':
                answers[name] = {'noul': a['probability']}
            else:
                probs = {str(p['value']): p['probability'] for p in a['probabilities']}
                if len(probs) != len(a['probabilities']):
                    raise InferenceError('duplicate_probability_keys')
                answers[name] = {kind: a[kind], 'probabilities': probs}
        return Prediction(answers, refused, raw.get('usage', {}), raw.get('model'))
