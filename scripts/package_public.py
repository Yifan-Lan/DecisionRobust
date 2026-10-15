"""Create a source-only archive from reviewed paths; never include Git history."""
import argparse
import json
import zipfile
from pathlib import Path

from audit_public_tree import audit, candidate_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(args.manifest.read_text())
    paths = manifest['paths']
    if len(paths) != len(set(paths)):
        raise ValueError('Duplicate paths in packaging manifest')
    report = audit(root, paths)
    if report['findings']:
        raise ValueError('Disclosure audit failed; inspect locations with audit_public_tree.py')
    hashes = {f['path']: f['sha256'] for f in report['files']}
    if hashes != manifest['sha256']:
        raise ValueError('Files changed since the reviewed manifest; re-audit before packaging')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(root / path, 'DecisionRobust/' + path)
    print(json.dumps({'files': len(paths), 'bytes': args.output.stat().st_size, 'git_history_included': False}))


if __name__ == '__main__':
    main()
