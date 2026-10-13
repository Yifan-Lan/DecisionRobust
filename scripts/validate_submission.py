"""Validate declarative community outputs against frozen public benchmark records.

Standard library only. Never imports or executes submitter code or downloads
submitter-supplied URLs. Format validation is not an authenticity endorsement.
"""
import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse

from submission_scoring import score, targeted_success

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r'^[a-z0-9][a-z0-9_-]{1,63}$')
INJECTION = {'text_injection_curated', 'image_overlay_curated', 'image_instruction_curated'}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def parse_json(raw):
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError('Duplicate JSON key: ' + k)
            obj[k] = v
        return obj
    def reject(value):
        raise ValueError('Non-finite JSON value: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject)


def load_json(path):
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('File exceeds 16 MiB limit')
    return parse_json(path.read_text())


def text(value, label, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Missing or invalid ' + label)


def https(value, label):
    text(value, label)
    u = urlparse(value)
    if u.scheme != 'https' or not u.netloc or u.username or u.password:
        raise ValueError(label + ' must be a public HTTPS reference without credentials')


def validate_answers(record, side, result):
    if not isinstance(result, dict):
        raise ValueError('Missing clean/adv output object')
    if result.get('request_sha256') != canonical_hash(record[side]):
        raise ValueError('Request hash mismatch for ' + side)
    status = result.get('status')
    if status in ('unsupported', 'error'):
        text(result.get('reason'), side + ' exclusion reason')
        return False
    if status != 'ok':
        raise ValueError('status must be ok, unsupported, or error')
    answers = result.get('answers')
    if not isinstance(answers, dict):
        raise ValueError('answers must be a question-ID map')
    # Unscored questions stay in the full request; only designated outputs score.
    for qid in record['task']['question_ids']:
        q = record[side]['questions'][qid]
        a = answers.get(qid)
        if not isinstance(a, dict):
            raise ValueError('Missing scored question output: ' + qid)
        kind = q['type']
        if kind == 'noul':
            value = a.get('noul')
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Invalid Noul probability')
        elif kind == 'score':
            value = a.get('score')
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= len(q['criteria'])-1:
                raise ValueError('Score must be finite and within the published scale')
        elif kind == 'choice' and a.get('choice') not in q['criteria']:
            raise ValueError('Invalid native Choice label')
        if 'probabilities' in a:
            probs = a['probabilities']
            expected = set(q['criteria']) if kind == 'choice' else {str(i) for i in range(len(q['criteria']))} if kind == 'score' else None
            if expected is None or not isinstance(probs, dict) or set(probs) != expected:
                raise ValueError('Probability keys do not match the question')
            vals = list(probs.values())
            if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in vals) or abs(sum(vals)-1) > 1e-4:
                raise ValueError('Invalid probability distribution')
            if kind == 'score':
                weighted = sum(int(k)*v for k,v in probs.items())
                if abs(weighted-a['score']) > 1e-4:
                    raise ValueError('Score differs from probability-weighted value')
    score(record, answers)
    return True


def validate_submission(folder, site_data=None):
    folder = Path(folder)
    if not SLUG.fullmatch(folder.name):
        raise ValueError('Submission folder must use a lowercase slug')
    site_data = Path(site_data or ROOT/'website/data')
    board = load_json(site_data/'leaderboard.json')
    index = load_json(site_data/'index.json')
    manifest = load_json(folder/'manifest.json')
    if manifest.get('schema_version') != 1:
        raise ValueError('Unknown submission schema version')
    release = manifest.get('release', {})
    for key in ['version', 'data_revision', 'results_revision']:
        if release.get(key) != board['release'][key]:
            raise ValueError('Release/target revision mismatch: ' + key)
    model = manifest.get('model', {})
    for key in ['name','revision','adapter','inference_settings','training_data_disclosure']:
        text(model.get(key), 'model.' + key)
    if not SLUG.fullmatch(model.get('id','')):
        raise ValueError('Invalid model ID')
    https(model.get('url'), 'model.url')
    https(manifest.get('evaluation_code_url'), 'evaluation_code_url')
    text(manifest.get('submitter'), 'submitter')
    if manifest.get('complete_requests_preserved') is not True:
        raise ValueError('Must attest to preserving full native requests')
    configs = manifest.get('configs')
    if not isinstance(configs,list) or not configs or len(configs)!=len(set(configs)) or any(c not in board['suites'] for c in configs):
        raise ValueError('Invalid or duplicate configs')
    expected = {(r['config'],r['id']) for r in index if r['config'] in configs}
    path = folder/'predictions.jsonl'
    if path.stat().st_size > 16*1024*1024:
        raise ValueError('predictions.jsonl exceeds 16 MiB')
    seen, scored = set(), collections.defaultdict(list)
    reasons = collections.defaultdict(collections.Counter)
    for line_number,line in enumerate(path.read_text().splitlines(),1):
        if not line.strip():
            continue
        try:
            row = parse_json(line)
            if type(row.get('id')) is not int:
                raise ValueError('Candidate ID must be an integer')
            key = (row.get('config'),row['id'])
            if key not in expected or key in seen:
                raise ValueError('Unknown or duplicate candidate ID/config')
            seen.add(key)
            record = load_json(site_data/'samples'/f'{row["id"]}.json')
            clean_ok = validate_answers(record, 'clean', row.get('clean'))
            adv_ok = validate_answers(record, 'adv', row.get('adv'))
            if not (clean_ok and adv_ok):
                reason = 'unsupported' if any(row[s]['status']=='unsupported' for s in ['clean','adv']) else 'error'
                reasons[key[0]][reason] += 1
                continue
            clean,adv = row['clean']['answers'],row['adv']['answers']
            c,a = score(record,clean),score(record,adv)
            flip = c['correct'] and not a['correct']
            success = flip
            if key[0] in INJECTION:
                target = board['injection_targets'][f'{key[0]}:{key[1]}']['target']
                success = targeted_success(record,target,clean,adv)['target_success']
            scored[key[0]].append((c['correct'],a['correct'],flip,success))
        except (ValueError,KeyError,TypeError) as exc:
            raise ValueError(f'Line {line_number}: {exc}') from exc
    if seen != expected:
        raise ValueError(f'Missing {len(expected-seen)} candidates; include explicit error/unsupported records')
    metrics=[]
    for config in configs:
        vals=scored[config];valid=len(vals);total=sum(c==config for c,_ in expected)
        if not valid:
            raise ValueError('No valid clean/adv pairs in ' + config)
        n=sum(v[0] for v in vals);clean=n;adv=sum(v[1] for v in vals)
        flip=sum(v[2] for v in vals);success=sum(v[3] for v in vals);inj=config in INJECTION
        metrics.append(dict(config=config,model=model['id'],model_name=model['name'],candidates=total,
            valid_pairs=valid,excluded_pairs=total-valid,denominator=n,successes=success,
            asr=success/n if n else None,clean_accuracy_on_valid_pairs=clean/valid,
            adv_accuracy_on_valid_pairs=adv/valid,used_for_selection=False,excluded_reasons=dict(reasons[config]),
            asr_type='targeted' if inj else 'untargeted',flip_successes=flip,flip_asr=flip/n if n else None,
            target_successes=success if inj else None,target_asr=success/n if n and inj else None,
            result_source='community_reviewed'))
    return dict(status='format_and_scoring_checks_passed',authenticity_verified=False,
                submission=folder.name,manifest=manifest,metrics=metrics,
                files_sha256={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                              for name in ['manifest.json','predictions.jsonl']})


def merge_approved(results, details, site_data):
    """Only the maintainer-controlled registry admits a submission to the site."""
    registry=load_json(ROOT/'submissions/approved.json')
    known={r['model'] for rows in results.values() for r in rows}
    for entry in registry['submissions']:
        slug=entry['submission']
        if not SLUG.fullmatch(slug):
            raise ValueError('Invalid approved submission path')
        if entry.get('reviewer')!='Yifan-Lan' or entry.get('verification') not in ['receipt_review','sample_rerun','full_rerun']:
            raise ValueError('Missing maintainer review or verification scope')
        https(entry.get('review_url'),'review_url');text(entry.get('reviewed_at'),'reviewed_at')
        checked=validate_submission(ROOT/'submissions/entries'/slug,site_data)
        if entry.get('files_sha256')!=checked['files_sha256']:
            raise ValueError('Reviewed files changed; new approval required')
        model=checked['manifest']['model'];mid=model['id']
        if mid in known:
            raise ValueError('Community submission cannot replace an existing model ID')
        known.add(mid)
        for metric in checked['metrics']:
            results[metric['config']].append(metric | {'verification':entry['verification']})
        details[mid]=dict(model,result_source='community_reviewed',review=entry,
                         submitter=checked['manifest']['submitter'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--site-data',type=Path,default=ROOT/'website/data')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=validate_submission(args.folder,args.site_data)
    data=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(data)
    print(data)


if __name__=='__main__':
    main()
