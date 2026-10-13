"""Create all candidate slots for a community evaluation (no inference)."""
import argparse
import json
from pathlib import Path
from validate_submission import ROOT, SLUG, canonical_hash, load_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('submission_id')
    p.add_argument('--configs',nargs='+',required=True)
    args=p.parse_args()
    if not SLUG.fullmatch(args.submission_id):p.error('Use a lowercase slug of 2–64 characters')
    data=ROOT/'website/data';board=load_json(data/'leaderboard.json')
    if len(args.configs)!=len(set(args.configs)) or any(c not in board['suites'] for c in args.configs):p.error('Unknown/duplicate suite')
    out=ROOT/'submissions/entries'/args.submission_id
    out.mkdir(parents=True,exist_ok=False)
    manifest=load_json(ROOT/'submissions/template/manifest.json')
    manifest['model']['id']=args.submission_id
    manifest['configs']=args.configs
    manifest['release']={k:board['release'][k] for k in ['version','data_revision','results_revision']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    n=0
    with (out/'predictions.jsonl').open('w') as f:
        for item in load_json(data/'index.json'):
            if item['config'] not in args.configs:continue
            record=load_json(data/'samples'/f'{item["id"]}.json')
            row={'config':item['config'],'id':item['id']}
            for side in ['clean','adv']:
                row[side]={'request_sha256':canonical_hash(record[side]),'status':'pending','answers':{}}
            f.write(json.dumps(row)+'\n');n+=1
    print(f'Created {n} pending candidate slots in {out}. Fill metadata and outputs; pending is not accepted by validation.')


if __name__=='__main__':main()
