"""Read JSON submission blobs from a PR without checking out or running PR code."""
import base64
import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path

from validate_submission import validate_submission

ROOT=Path(__file__).resolve().parents[1]
REPO='Yifan-Lan/DecisionRobust'
BASE='https://api.github.com/repos/'+REPO


def get(url):
    if not url.startswith(BASE+'/'):
        raise ValueError('Only this repository API may be requested')
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],
        'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(req,timeout=30) as response:
        raw=response.read(24*1024*1024+1)
    if len(raw)>24*1024*1024:
        raise ValueError('API response too large')
    return json.loads(raw)


def main():
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    pr=event['pull_request'];number=pr['number'];head=pr['head']['sha']
    assert re.fullmatch(r'[0-9a-f]{40}',head)
    files=[]
    for page in range(1,6):
        batch=get(f'{BASE}/pulls/{number}/files?per_page=100&page={page}')
        files+=batch
        if len(batch)<100:break
    else:raise ValueError('PR exceeds automated review size limit')
    pattern=re.compile(r'^submissions/entries/([a-z0-9][a-z0-9_-]{1,63})/(manifest\.json|predictions\.jsonl)$')
    slugs=set()
    for f in files:
        match=pattern.fullmatch(f['filename'])
        if match and f['status']!='removed':slugs.add(match[1])
    if not slugs:raise ValueError('No submission manifest/predictions to validate')
    if len(slugs)>5:raise ValueError('At most five submissions per PR')
    out=ROOT/'submission-checks';out.mkdir(exist_ok=True)
    reports=[];failed=False
    with tempfile.TemporaryDirectory() as temp:
        for slug in sorted(slugs):
            try:
                folder=Path(temp)/slug;folder.mkdir()
                for name in ['manifest.json','predictions.jsonl']:
                    record=get(f'{BASE}/contents/submissions/entries/{slug}/{name}?ref={head}')
                    if record['type']!='file' or record['size']>16*1024*1024:raise ValueError('Unsupported file type or size')
                    blob=get(f'{BASE}/git/blobs/{record["sha"]}')
                    if blob.get('encoding')!='base64':raise ValueError('Unexpected blob encoding')
                    content=base64.b64decode(blob['content'])
                    if len(content)!=record['size']:raise ValueError('Blob size mismatch')
                    (folder/name).write_bytes(content)
                report=validate_submission(folder)
            except Exception as exc:
                failed=True;report={'submission':slug,'status':'failed','error':str(exc)}
            (out/(slug+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            reports.append({'submission':slug,'status':report['status']})
    print(json.dumps({'pull_request':number,'head_sha':head,'checks':reports}))
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as f:
        f.write('## Submission checks\n\nChecks never publish results. Maintainer review is still required.\n\n')
        for r in reports:f.write(f'- `{r["submission"]}`: {r["status"]}\n')
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
