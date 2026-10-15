import copy
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from decisionrobust.data import Release, safe_path
from decisionrobust.evaluation.runner import load_journal, run
from decisionrobust.io import atomic_json, digest, loads, read_json
from decisionrobust.models import request_key
from decisionrobust.models.base import Adapter, InferenceError, Prediction
from decisionrobust.models.http import NativeHTTP, OpenAIDecisions
from decisionrobust.scoring import aggregate, evaluate_pair, score, validate_scored_answers


SUITE = 'text_adversarial_curated'


def record(mode='choice'):
    q = {'type': mode, 'instructions': 'Evaluate the supplied state.'}
    task = {'mode': mode, 'question_ids': ['q']}
    gt = 'A'
    if mode == 'choice':
        q['criteria'] = {'A': 'First', 'B': 'Second'}
    elif mode == 'score':
        q['criteria'] = ['low', 'middle', 'high']
        gt = 0
    else:
        task.update(labels=[False, True], positive_label=True)
        gt = True
    clean = {'state': 'Example input', 'questions': {'q': q,
              'unscored': {'type': 'noul', 'instructions': 'An unscored question'}}}
    adv = copy.deepcopy(clean)
    adv['state'] = 'Edited example input'
    return {'id': 0, 'original_id': 0, 'source': 'synthetic', 'scenario': 'unit_test',
            'clean': clean, 'adv': adv, 'task': task, 'gt': gt, 'attack': 'synthetic'}


class FakeRelease:
    pins = {'version': 'test'}

    def __init__(self, records=None):
        self.rows = records or [record()]

    def records(self, suite):
        return copy.deepcopy(self.rows)

    def targets(self):
        return {('text_injection_curated', r['id']): {'question_ids': ['q'], 'target': 'B'} for r in self.rows}

    def image(self, suite, path):
        return path.encode(), hashlib.sha256(path.encode()).hexdigest()


class Stub(Adapter):
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def predict(self, request, images):
        self.calls.append(copy.deepcopy(request))
        assert set(request['questions']) == {'q', 'unscored'}
        assert 'gt' not in request and 'target' not in request
        if self.fail and request['state'].startswith('Edited'):
            raise InferenceError('temporary', retryable=True)
        return Prediction({'q': {'choice': 'B' if request['state'].startswith('Edited') else 'A'}}, ['unscored'])


CONFIG = {'id': 'synthetic', 'adapter': 'python', 'revision': 'test'}


class ScoringTests(unittest.TestCase):
    def test_native_choice_over_argmax(self):
        r = record()
        answers = {'q': {'choice': 'A', 'probabilities': {'A': .1, 'B': .9}}}
        validate_scored_answers(r, 'clean', answers)
        self.assertTrue(score(r, answers)['correct'])

    def test_score_expectation_and_tolerance(self):
        r = record('score')
        self.assertTrue(score(r, {'q': {'score': .5}})['correct'])
        self.assertFalse(score(r, {'q': {'score': .5001}})['correct'])
        with self.assertRaises(ValueError):
            validate_scored_answers(r, 'clean', {'q': {'score': 0, 'probabilities': {'0': .6, '1': .4, '2': 0}}})
        for value in [True, float('nan'), -1, 3]:
            with self.assertRaises(ValueError):
                validate_scored_answers(r, 'clean', {'q': {'score': value}})

    def test_noul(self):
        r = record('noul')
        self.assertTrue(score(r, {'q': {'noul': .5}})['correct'])
        r['task'] = {'mode': 'noul', 'question_ids': ['q', 'r'], 'labels': ['A', 'B']}
        r['gt'] = 'A'
        self.assertEqual(score(r, {'q': {'noul': 0}, 'r': {'noul': 0}})['prediction'], 'A')
        self.assertEqual(score(r, {'q': {'noul': .2}, 'r': {'noul': .3}})['prediction'], 'B')

    def test_target_requires_wrong_answer_and_clean_correct(self):
        r = record('score')
        clean = {'status': 'ok', 'answers': {'q': {'score': 0}}}
        adv = {'status': 'ok', 'answers': {'q': {'score': .5}}}
        self.assertFalse(evaluate_pair(r, clean, adv, target=1, injection=True)['success'])
        adv['answers']['q']['score'] = 1.1
        self.assertTrue(evaluate_pair(r, clean, adv, target=1, injection=True)['success'])
        clean['answers']['q']['score'] = 2
        self.assertFalse(evaluate_pair(r, clean, adv, target=1, injection=True)['eligible'])

    def test_refusals_missing_errors_and_zero_denominators(self):
        r = record()
        clean = {'status': 'ok', 'answers': {'q': {'choice': 'A'}}, 'refused': ['unscored']}
        adv = {'status': 'ok', 'answers': {'q': {'choice': 'B'}}}
        self.assertTrue(evaluate_pair(r, clean, adv)['success'])
        for invalid in [None, {'status': 'error'}, {'status': 'ok', 'answers': {}},
                        dict(adv, refused=['q'])]:
            row = evaluate_pair(r, clean, invalid)
            self.assertFalse(row['valid'])
            self.assertIsNone(aggregate([row])['asr'])


class RunnerTests(unittest.TestCase):
    def test_dedup_resume_and_candidate_weighting(self):
        records = [record(), dict(record(), id=1)]
        with tempfile.TemporaryDirectory() as d:
            model = Stub()
            summary = run(FakeRelease(records), [SUITE], model, CONFIG, d, requests_per_second=10000)
            self.assertEqual(len(model.calls), 2)
            self.assertEqual(summary['by_config'][SUITE]['denominator'], 2)
            self.assertEqual(summary['by_config'][SUITE]['asr'], 1)
            run(FakeRelease(records), [SUITE], model, CONFIG, d, requests_per_second=10000)
            self.assertEqual(len(model.calls), 2)
            with self.assertRaisesRegex(ValueError, 'binding mismatch'):
                run(FakeRelease(records), [SUITE], model, dict(CONFIG, revision='other'), d)

    def test_retry_only_failed(self):
        with tempfile.TemporaryDirectory() as d:
            model = Stub(fail=True)
            run(FakeRelease(), [SUITE], model, CONFIG, d, attempts=1, requests_per_second=10000)
            model.fail = False
            result = run(FakeRelease(), [SUITE], model, CONFIG, d, retry_failed=True, requests_per_second=10000)
            self.assertEqual(len(model.calls), 3)
            self.assertEqual(result['by_config'][SUITE]['valid_pairs'], 1)

    def test_changed_pixels_invalidate_key(self):
        r = record()['clean']
        self.assertNotEqual(request_key(r, [b'one']), request_key(r, [b'two']))

    def test_torn_tail_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'requests.jsonl'
            p.write_bytes(b'{"request_key":"ok","status":"ok"}\n{"request_key":')
            self.assertEqual(set(load_journal(p)), {'ok'})
            self.assertTrue(p.read_bytes().endswith(b'\n'))
            p.write_bytes(b'broken\n')
            with self.assertRaises(ValueError):
                load_journal(p)

    def test_unsafe_concurrency_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                run(FakeRelease(), [SUITE], Stub(), CONFIG, d, workers=2)

    def test_injection_denominator_counts_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            suite = 'text_injection_curated'
            result = run(FakeRelease(), [suite], Stub(), CONFIG, d, requests_per_second=10000)
            self.assertEqual(result['by_config'][suite]['asr_type'], 'targeted')
            self.assertEqual(result['by_config'][suite]['successes'], 1)

    def test_run_lock_prevents_concurrent_writers(self):
        import fcntl
        with tempfile.TemporaryDirectory() as d:
            with (Path(d) / '.run.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    run(FakeRelease(), [SUITE], Stub(), CONFIG, d)


class DataAndTransportTests(unittest.TestCase):
    def test_path_and_json_boundaries(self):
        for path in ['../private', '/private', 'https://example.org/image', 'a\\b']:
            with self.assertRaises(ValueError):
                safe_path('.', path)
        for raw in ['{"a":1,"a":2}', '{"a":NaN}']:
            with self.assertRaises(ValueError):
                loads(raw)

    def test_hash_verification(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d);p = root / 'raw' / SUITE / 'data.jsonl';p.parent.mkdir(parents=True)
            p.write_text(json.dumps(record()) + '\n')
            relative = p.relative_to(root).as_posix()
            atomic_json(root / 'MANIFEST.json', {'files': {relative: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}}})
            pins = {'data_revision': 'a'*40, 'results_revision': 'b'*40}
            release = Release(root, pins)
            self.assertEqual(len(release.records(SUITE)), 1)
            p.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                release.records(SUITE)

    def test_openai_mapping_preserves_full_questions_and_pixels(self):
        model = OpenAIDecisions({'endpoint': 'http://127.0.0.1:8000', 'model': 'test'})
        body = record()['adv'];before = copy.deepcopy(body)
        image = b'\x89PNG\r\n\x1a\nsynthetic'
        payload = model.payload(body, [image])
        self.assertEqual(body, before)
        self.assertEqual({q['name'] for q in payload['questions']}, {'q', 'unscored'})
        self.assertNotIn('gt', payload)
        import base64
        self.assertEqual(base64.b64decode(payload['input'][0]['content'][1]['image_url'].split(',')[1]), image)
        raw = {'model': 'returned', 'answers': [
            {'name': 'q', 'type': 'choice', 'choice': 'A', 'probabilities': [{'value': 'A', 'probability': .3}, {'value': 'B', 'probability': .7}]},
            {'name': 'unscored', 'type': 'refusal'}]}
        prediction = model.normalize(body, raw)
        self.assertEqual(prediction.answers['q']['choice'], 'A')
        self.assertEqual(prediction.refused, ['unscored'])

    def test_endpoint_credentials_and_redirects_rejected(self):
        for endpoint in ['http://remote.example/api', 'https://' + 'user:pass' + '@example.org/api', 'https://example.org/api?token=x']:
            with self.assertRaises(ValueError):
                NativeHTTP({'endpoint': endpoint})
        from decisionrobust.models.http import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.example/'))

    def test_local_http_redaction_and_transient_failure(self):
        key = 'synthetic-' + 'credential-for-local-test'
        observed = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                observed.append(body)
                if len(observed) == 1:
                    self.send_response(429)
                    self.send_header('Retry-After', '0')
                    self.end_headers()
                    self.wfile.write(key.encode())
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'answers': {'q': {'choice': 'A'}, 'unscored': {'noul': .2}},
                    'model': key, 'usage': {}}).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict('os.environ', {'TEST_MODEL_CREDENTIAL': key}):
                adapter = NativeHTTP({'endpoint': f'http://127.0.0.1:{server.server_port}',
                                      'api_key_env': 'TEST_MODEL_CREDENTIAL'})
                with self.assertRaises(InferenceError) as ctx:
                    adapter.predict(record()['clean'], [])
                self.assertTrue(ctx.exception.retryable)
                self.assertNotIn(key, str(ctx.exception))
                prediction = adapter.predict(record()['clean'], [])
                self.assertEqual(prediction.model, '[REDACTED]')
                self.assertEqual(observed[-1], record()['clean'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_site_and_package_pin_agreement(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(read_json(root / 'site_config.json'), read_json(root / 'src/decisionrobust/release.json'))


if __name__ == '__main__':
    unittest.main()
