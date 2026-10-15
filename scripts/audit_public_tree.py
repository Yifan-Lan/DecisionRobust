"""Read-only disclosure scan. Reports locations/categories, never matched secrets.

This is a conservative automated check, not proof that a release is risk-free.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

RULES = {
    'credential_token': re.compile(rb'(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|hf_[A-Za-z0-9]{25,}|liquid_[A-Za-z0-9]{25,}|apikey_[a-f0-9]{24,}_[a-f0-9]{24,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential_in_url': re.compile(rb'https?://[^\s/:]+:[^\s/@]+@'),
    'private_machine_path': re.compile(rb'(?:/data/(?:home/)?[a-zA-Z]+[0-9]+/|/home/[a-zA-Z]+[0-9]+/|/Us' + rb'ers/[^/\s]+/|[A-Z]:\\Users\\[^\\\s]+\\)'),
    'cloud_account_endpoint': re.compile(rb'https://[a-zA-Z0-9-]+\.(?:openai\.azure\.com|services\.ai\.azure\.com)'),
    'literal_secret_assignment': re.compile(rb'''(?i)(?:api_key|access_token|password|client_secret)\s*[:=]\s*["'][A-Za-z0-9_+/.=-]{24,}["']'''),
}
FORBIDDEN_SUFFIXES = {'.key', '.pem', '.p12', '.pfx', '.safetensors', '.pt', '.pth', '.bin', '.pyc', '.log'}
FORBIDDEN_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', 'checkpoints', 'cache', 'runs', 'downloads'}


def findings(path, raw):
    found = []
    for rule, pattern in RULES.items():
        for match in pattern.finditer(raw):
            found.append({'path': path, 'rule': rule, 'line': raw.count(b'\n', 0, match.start()) + 1})
    return found


def candidate_files(root):
    # gitignore is necessary but not sufficient; packaging also uses an explicit manifest.
    if (root / '.git').exists():
        output = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'])
        return sorted(set(p.decode() for p in output.split(b'\0') if p and (root / p.decode()).exists()))
    # Source ZIPs have no .git. Match generated-directory exclusions so that
    # following the documented test/install/demo sequence does not package caches.
    # Credential files are NOT excluded here; unexpected .env/key files still fail.
    generated = FORBIDDEN_DIRS | {'build', 'dist', 'submission-checks'}
    paths = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            path = parent / name
            if path.is_symlink():
                paths.append(path.relative_to(root).as_posix())
                dirs.remove(name)
            elif name in generated or name.endswith('.egg-info') or path == root / 'website/data':
                dirs.remove(name)
        paths.extend((parent / name).relative_to(root).as_posix() for name in files if name != '.DS_Store')
    return sorted(paths)


def audit(root, paths):
    issues, files = [], []
    root = root.resolve()
    for relative in paths:
        p = root / relative
        if p.is_symlink() or not p.resolve().is_relative_to(root):
            issues.append({'path': relative, 'rule': 'symlink_or_path_escape'})
            continue
        if p.suffix.lower() in FORBIDDEN_SUFFIXES or set(Path(relative).parts) & FORBIDDEN_DIRS:
            issues.append({'path': relative, 'rule': 'private_or_generated_artifact'})
        if p.name.startswith('.env') and p.name != '.env.example':
            issues.append({'path': relative, 'rule': 'environment_file'})
        if p.stat().st_size > 10 * 1024 * 1024:
            issues.append({'path': relative, 'rule': 'large_file_requires_review'})
        raw = p.read_bytes()
        issues += findings(relative, raw)
        files.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    return {'files_scanned': len(files), 'total_bytes': sum(x['bytes'] for x in files), 'findings': issues, 'files': files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--manifest', type=Path, help='Scan only paths from the reviewed packaging manifest')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = json.loads(args.manifest.read_text())['paths'] if args.manifest else candidate_files(args.root)
    result = audit(args.root, paths)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
    raise SystemExit(bool(result['findings']))


if __name__ == '__main__':
    main()
