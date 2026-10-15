import copy
import fcntl
import importlib.metadata
import inspect
import json
import math
import platform
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .. import __version__
from ..data import INJECTION
from ..io import append_jsonl, atomic_json, digest, file_hash, loads, read_json
from ..models import request_key
from ..models.base import InferenceError, Prediction, UnsupportedInput
from ..scoring import aggregate, evaluate_pair, validate_scored_answers


class RateLimiter:
    def __init__(self, rate):
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError('requests_per_second must be finite and positive')
        self.interval, self.next, self.lock = 1 / rate, 0., threading.Lock()

    def wait(self, halt):
        with self.lock:
            now = time.monotonic()
            delay = max(0., self.next - now)
            self.next = max(now, self.next) + self.interval
        return not halt.wait(delay)


def code_fingerprint(adapter):
    root = Path(__file__).parents[1]
    hashes = {str(p.relative_to(root)): file_hash(p) for p in sorted(root.rglob('*.py'))}
    path = inspect.getsourcefile(type(adapter))
    if path:
        hashes['adapter_implementation'] = file_hash(path)
    return digest(hashes)


def load_journal(path):
    """Only a final unterminated write can be repaired. Other corruption is fatal."""
    path = Path(path)
    cache = {}
    if not path.exists():
        return cache
    with path.open('r+b') as stream:
        while True:
            offset = stream.tell()
            line = stream.readline()
            if not line:
                break
            if not line.endswith(b'\n'):
                stream.truncate(offset)
                break
            row = loads(line)
            cache[row['request_key']] = row
    return cache


def prepare(release, suites, limit=None):
    if not suites or len(suites) != len(set(suites)):
        raise ValueError('Choose each suite exactly once')
    records, queries, references = [], {}, {}
    targets = release.targets() if set(suites) & INJECTION else {}
    for suite in suites:
        selected = release.records(suite)
        if limit is not None:
            selected = selected[:limit]
        for record in selected:
            entry = {'config': suite, 'record': record, 'keys': {}}
            if suite in INJECTION:
                target = targets[(suite, record['id'])]
                if target['question_ids'] != record['task']['question_ids'] or target['target'] == record['gt']:
                    raise ValueError('Invalid injection target binding')
                entry['target'] = target['target']
            for side in ('clean', 'adv'):
                request = record[side]
                images = [release.image(suite, p)[0] for p in request.get('images', [])]
                key = request_key(request, images)
                queries.setdefault(key, (request, images))
                references.setdefault(key, []).append((record, side))
                entry['keys'][side] = key
            records.append(entry)
    return records, queries, references


def report(records, cache, output):
    rows, predictions = [], []
    for entry in records:
        r, suite = entry['record'], entry['config']
        sides = {side: cache.get(key) for side, key in entry['keys'].items()}
        outcome = evaluate_pair(r, sides['clean'], sides['adv'], entry.get('target'), suite in INJECTION)
        rows.append({'config': suite, 'id': r['id'], 'original_id': r['original_id'],
                     'source': r['source'], 'scenario': r['scenario'], 'attack': r['attack'],
                     'mode': r['task']['mode'], **outcome})
        # Matches the existing community submission format; incomplete runs keep pending.
        predictions.append({'config': suite, 'id': r['id'], **{
            side: {'request_sha256': digest(r[side]), **({k: v for k, v in (sides[side] or {}).items()
                    if k in ('status', 'answers', 'reason')} if sides[side] else {'status': 'pending'})}
            for side in ('clean', 'adv')}})
        for side in ('clean', 'adv'):
            if sides[side] and set(r['task']['question_ids']) & set(sides[side].get('refused', [])):
                predictions[-1][side] = {'request_sha256': digest(r[side]), 'status': 'error', 'reason': 'refusal'}
    summary = {'by_config': {}, 'by_group': {}}
    for suite in sorted({r['config'] for r in rows}):
        group = [r for r in rows if r['config'] == suite]
        summary['by_config'][suite] = dict(aggregate(group), asr_type='targeted' if suite in INJECTION else 'untargeted')
        summary['by_group'][suite] = {field: {
            value: aggregate([r for r in group if r[field] == value]) for value in sorted({r[field] for r in group})
        } for field in ('source', 'scenario', 'attack', 'mode')}
    atomic_json(output / 'summary.json', summary)
    # Small public panels; atomically materialize exports after durable request journaling.
    for name, values in (('predictions.jsonl', predictions), ('outcomes.jsonl', rows)):
        temp = output / ('.' + name)
        temp.write_text(''.join(json.dumps(v, ensure_ascii=False, allow_nan=False) + '\n' for v in values), encoding='utf-8')
        temp.replace(output / name)
    return summary


def run(release, suites, adapter, model_config, output, *, workers=1, requests_per_second=1.,
        attempts=3, retry_failed=False, limit=None):
    if workers < 1 or attempts < 1 or (limit is not None and limit < 1):
        raise ValueError('Workers, attempts and limit must be positive')
    if workers > 1 and not adapter.thread_safe:
        raise ValueError('This adapter requires workers=1')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    lock = (output / '.run.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(release, suites, adapter, model_config, output, workers, requests_per_second,
                    attempts, retry_failed, limit)
    finally:
        lock.close()


def _run(release, suites, adapter, model_config, output, workers, rate, attempts, retry_failed, limit):
    records, queries, references = prepare(release, suites, limit)
    runtime = {'python': platform.python_version(), 'package': __version__}
    for package in ('torch', 'transformers', 'kev', 'peft', 'typesafe-sdk'):
        try:
            runtime[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    binding = {'release': release.pins, 'suites': suites, 'model_config_sha256': digest(model_config),
               'code_sha256': code_fingerprint(adapter), 'runtime': runtime,
               'records_sha256': digest(records), 'limit': limit, 'request_keys': sorted(queries)}
    manifest = output / 'run.json'
    if manifest.exists() and read_json(manifest)['binding'] != binding:
        raise ValueError('Resume binding mismatch; use a different output directory')
    atomic_json(manifest, {'binding': binding, 'model_id': model_config['id'],
        'model_revision': model_config['revision'], 'adapter': model_config['adapter'],
        'settings': {k: v for k, v in model_config.items() if k not in ('endpoint', 'checkpoint', 'receipts')},
        'execution': {'workers': workers, 'requests_per_second': rate, 'attempts': attempts}})
    journal = output / 'requests.jsonl'
    cache = load_journal(journal)
    if set(cache) - set(queries):
        raise ValueError('Unknown request in checkpoint journal')
    pending = [key for key in queries if key not in cache or (retry_failed and cache[key]['status'] == 'error')]
    halt, limiter = threading.Event(), RateLimiter(rate)

    def call(key):
        request, images = queries[key]
        start = time.monotonic()
        for attempt in range(1, attempts + 1):
            if not limiter.wait(halt):
                return None
            result = {'request_key': key, 'attempts': attempt}
            try:
                prediction = adapter.predict(copy.deepcopy(request), images)
                if not isinstance(prediction, Prediction):
                    raise InferenceError('invalid_adapter_contract')
                for record, side in references[key]:
                    if not set(record['task']['question_ids']) & set(prediction.refused):
                        validate_scored_answers(record, side, prediction.answers)
                result.update(status='ok', answers=prediction.answers, refused=prediction.refused,
                              usage=prediction.usage, actual_model=prediction.model)
            except UnsupportedInput:
                result.update(status='unsupported', reason='unsupported_input')
            except InferenceError as exc:
                result.update(status='error', reason=exc.code)
                if exc.code in ('http_401', 'http_402', 'http_403'):
                    halt.set()
                if exc.retryable and attempt < attempts:
                    if not halt.wait(min(60., exc.retry_after if exc.retry_after is not None else 2 ** (attempt - 1))):
                        continue
            except (ValueError, KeyError, TypeError):
                result.update(status='error', reason='invalid_output')
            except Exception:
                # Do not write exception messages containing paths, prompts, or credentials.
                result.update(status='error', reason='adapter_exception')
            result['elapsed_seconds'] = time.monotonic() - start
            return result

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(call, key) for key in pending]
    try:
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                append_jsonl(journal, result)
                cache[result['request_key']] = result
                atomic_json(output / 'progress.json', {'completed_requests': len(cache),
                    'expected_requests': len(queries), 'errors': sum(v['status'] == 'error' for v in cache.values()),
                    'halted': halt.is_set()})
    except BaseException:
        halt.set()
        # Stop queued work and let bounded-time in-flight calls finish.
        pool.shutdown(wait=True, cancel_futures=True)
        for future in futures:
            if not future.cancelled() and future.done() and future.exception() is None:
                result = future.result()
                if result is not None and cache.get(result['request_key']) != result:
                    append_jsonl(journal, result)
                    cache[result['request_key']] = result
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        report(records, cache, output)
    return read_json(output / 'summary.json')
