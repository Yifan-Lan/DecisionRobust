"""End-to-end synthetic demo. No network, credentials, model weights or GPU needed."""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from decisionrobust.data import Release
from decisionrobust.evaluation.runner import run
from decisionrobust.io import atomic_json
from decisionrobust.models import Replay, request_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='runs/offline-demo')
    args = parser.parse_args()
    out = Path(args.output)
    root = out / 'synthetic-release'
    suite = 'text_adversarial_curated'
    clean = {'state': 'A synthetic item for testing the software.', 'questions': {
        'q': {'type': 'choice', 'instructions': 'Choose the first category.', 'criteria': {'A': 'First', 'B': 'Second'}},
        'extra': {'type': 'noul', 'instructions': 'This question has no scored GT.'}}}
    adv = copy.deepcopy(clean)
    adv['state'] = 'A synthetically edited item for testing the software.'
    record = {'id': 0, 'original_id': 0, 'source': 'synthetic-demo', 'scenario': 'software-test',
              'clean': clean, 'adv': adv, 'gt': 'A', 'task': {'mode': 'choice', 'question_ids': ['q']},
              'attack': 'synthetic-demo-not-a-measured-attack'}
    path = root / 'raw' / suite / 'data.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record) + '\n')
    atomic_json(root / 'MANIFEST.json', {'files': {f'raw/{suite}/data.jsonl': {
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}})
    receipts = out / 'synthetic-receipts.jsonl'
    receipts.write_text(''.join(json.dumps({'request_key': request_key(body, []),
        'answers': {'q': {'choice': label}, 'extra': {'noul': .5}}, 'model': 'synthetic-replay'}) + '\n'
        for body, label in [(clean, 'A'), (adv, 'B')]))
    config = {'id': 'synthetic-replay', 'adapter': 'replay', 'revision': 'synthetic-v1', 'receipts': str(receipts)}
    atomic_json(out / 'replay-config.json', config)
    pins = {'version': 'synthetic', 'dataset': 'synthetic/demo', 'data_revision': 'a'*40, 'results_revision': 'b'*40}
    release = Release(root, pins)
    result = run(release, [suite], Replay(config), config, out / 'evaluation', requests_per_second=10000)
    print('Synthetic software test only; these are NOT benchmark/model measurements.')
    print(json.dumps(result['by_config'], indent=2))


if __name__ == '__main__':
    main()
