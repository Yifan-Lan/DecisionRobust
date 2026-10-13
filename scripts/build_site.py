"""Build a static website snapshot from pinned, public Hugging Face files."""
import argparse
import csv
import hashlib
import json
import pathlib
import shutil
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'site_config.json').read_text())
SUITES = {
    'text_adversarial_curated': ('Text adversarial', 'Meaning-preserving edits to text and structured inputs.'),
    'text_injection_curated': ('Text injection', 'Output-hijacking instructions in text and structured inputs.'),
    'image_perturbation_curated': ('Image perturbation', 'Common corruptions and optimization-based image perturbations.'),
    'image_overlay_curated': ('Image overlay', 'Instruction text embedded in the image.'),
    'image_instruction_curated': ('Image instruction', 'Injection appended to the question accompanying an image.'),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', type=pathlib.Path, help='Optional local copy of the published release')
    args = parser.parse_args()
    def read(path, revision):
        if args.release_dir:
            return (args.release_dir / path).read_bytes()
        url = f'https://huggingface.co/datasets/{CONFIG["dataset"]}/resolve/{revision}/{path}'
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    manifests = {rev: json.loads(read('MANIFEST.json', rev)) for rev in {CONFIG['data_revision'], CONFIG['results_revision']}}
    def checked(path, rev):
        data = read(path, rev)
        expected = manifests[rev]['files'][path]['sha256']
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Hash mismatch: {path}')
        return data
    results = json.loads(checked('results/asr.json', CONFIG['results_revision']))
    details = json.loads(checked('results/model_details.json', CONFIG['results_revision']))
    targets = json.loads(checked('results/injection_targets.json', CONFIG['results_revision']))
    target_map = {f"{r['config']}:{r['id']}": r for r in targets}
    assert len(target_map) == len(targets) == 717
    info = json.loads(checked('dataset_info.json', CONFIG['data_revision']))
    out = ROOT / 'website/data'
    if out.exists():
        shutil.rmtree(out)
    (out / 'samples').mkdir(parents=True)
    def write(path, data):
        (out / path).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    index, seen, originals = [], set(), set()
    for config in SUITES:
        rows = [json.loads(line) for line in checked(f'raw/{config}/data.jsonl', CONFIG['data_revision']).decode().splitlines() if line]
        assert len(rows) == info['collections'][config]['candidates']
        for row in rows:
            assert row['id'] not in seen, 'Duplicate public candidate ID'
            seen.add(row['id']); originals.add(row['original_id'])
            if config.endswith(('injection_curated', 'overlay_curated', 'instruction_curated')):
                t = target_map[f"{config}:{row['id']}"]
                assert t['target'] != row['gt'] and t['question_ids'] == row['task']['question_ids']
            assert all(q in row['clean']['questions'] and q in row['adv']['questions'] for q in row['task']['question_ids'])
            # Native requests remain unchanged; image base URL is supplied separately.
            write(f'samples/{row["id"]}.json', row)
            index.append({k: row[k] for k in ['id', 'original_id', 'source', 'scenario', 'attack']} | {'config': config, 'mode': row['task']['mode']})
        for r in results[config]:
            expected_type = 'targeted' if config in {'text_injection_curated','image_overlay_curated','image_instruction_curated'} else 'untargeted'
            assert r['asr_type'] == expected_type
            assert r['successes'] <= r['flip_successes']
            if expected_type == 'targeted': assert r['asr'] == r['target_asr'] and r['successes'] == r['target_successes']
            assert 0 <= r['successes'] <= r['denominator'] <= r['valid_pairs'] <= len(rows)
            assert r['valid_pairs'] + r['excluded_pairs'] == r['candidates'] == len(rows)
            if r['denominator']:
                assert abs(r['asr'] - r['successes'] / r['denominator']) < 1e-9
    models = {r['model']: r['model_name'] for rows in results.values() for r in rows}
    assert len(index) == info['candidates'] and len(originals) == info['original_questions']
    write('index.json', index)
    write('leaderboard.json', {'release': CONFIG, 'suites': SUITES, 'info': info, 'results': results, 'models': models, 'model_details': details, 'injection_targets': target_map})
    # Pending entries never affect rankings. Reviewed hashes pin each admitted file.
    from validate_submission import merge_approved
    merge_approved(results, details, out)
    models = {r['model']: r['model_name'] for rows in results.values() for r in rows}
    write('leaderboard.json', {'release': CONFIG, 'suites': SUITES, 'info': info, 'results': results, 'models': models, 'model_details': details, 'injection_targets': target_map})
    (out / 'asr.csv').write_bytes(checked('results/asr.csv', CONFIG['results_revision']))
    if any(r.get('result_source') == 'community_reviewed' for rows in results.values() for r in rows):
        flat = [r for rows in results.values() for r in rows]
        fields = list(dict.fromkeys(k for r in flat for k in r))
        def cell(v):
            if isinstance(v, (dict,list)): v = json.dumps(v,ensure_ascii=False)
            return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v
        with (out/'asr.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            writer.writerows({k:cell(v) for k,v in r.items()} for r in flat)
    (out / 'CITATION.bib').write_bytes(checked('CITATION.bib', CONFIG['results_revision']))
    print(f'Built {len(index)} candidates, {len(originals)} originals, {len(models)} models. All source hashes and metric bounds verified.')

if __name__ == '__main__':
    main()
