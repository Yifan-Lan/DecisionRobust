"""Load immutable native JSONL and original image bytes from the public release."""
import hashlib
import re
import urllib.request
from pathlib import Path, PurePosixPath

from ..io import atomic_json, loads, read_json

SUITES = ('text_adversarial_curated', 'text_injection_curated',
          'image_perturbation_curated', 'image_overlay_curated', 'image_instruction_curated')
INJECTION = frozenset(SUITES[i] for i in (1, 3, 4))


def safe_path(root, relative):
    if not isinstance(relative, str) or '\\' in relative:
        raise ValueError('Expected a relative POSIX path')
    p = PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts or not p.parts or ':' in relative:
        raise ValueError('Unsafe release path')
    root = Path(root).resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Release path escapes its directory')
    return result


def decode_record(row):
    """Decode the native fields of a HF Parquet row, ignoring viewer-only columns."""
    fields = ('id', 'original_id', 'source', 'scenario', 'clean', 'adv', 'gt', 'task', 'attack')
    return {k: loads(row[k]) if k in ('clean', 'adv', 'gt', 'task') and isinstance(row[k], str)
            else row[k] for k in fields}


class Release:
    def __init__(self, root=None, pins=None, cache_dir=None):
        self.pins = pins or read_json(Path(__file__).parents[1] / 'release.json')
        self.root = Path(root).resolve() if root else None
        self.cache = Path(cache_dir or Path.home() / '.cache' / 'decisionrobust')
        self.manifests = {}
        for rev in (self.pins['data_revision'], self.pins['results_revision']):
            if not re.fullmatch('[0-9a-f]{40}', rev):
                raise ValueError('Use immutable 40-character release revisions')

    def _fetch(self, path, rev):
        if self.root:
            return safe_path(self.root, path).read_bytes()
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', self.pins['dataset']):
            raise ValueError('Invalid dataset repository')
        # Validate paths even for remote access.
        dest = safe_path(self.cache / rev, path)
        if dest.exists():
            return dest.read_bytes()
        url = f"https://huggingface.co/datasets/{self.pins['dataset']}/resolve/{rev}/{path}"
        with urllib.request.urlopen(url, timeout=120) as response:
            raw = response.read()
        return raw

    def checked(self, path, results=False):
        rev = self.pins['results_revision' if results else 'data_revision']
        if rev not in self.manifests:
            self.manifests[rev] = loads(self._fetch('MANIFEST.json', rev))
        expected = self.manifests[rev]['files'][path]['sha256']
        raw = self._fetch(path, rev)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Release SHA256 mismatch: ' + path)
        if not self.root:
            dest = safe_path(self.cache / rev, path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Atomic replace; readers never observe partial images/JSONL.
            import tempfile, os
            fd, temporary = tempfile.mkstemp(dir=dest.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
                os.replace(temporary, dest)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return raw

    def records(self, suite):
        if suite not in SUITES:
            raise ValueError('Unknown suite')
        rows = [loads(line) for line in self.checked(f'raw/{suite}/data.jsonl').splitlines() if line.strip()]
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate candidate IDs')
        for row in rows:
            qids = row['task']['question_ids']
            if not qids or len(qids) != len(set(qids)):
                raise ValueError('Invalid scoring targets')
            for side in ('clean', 'adv'):
                if not set(qids) <= row[side]['questions'].keys():
                    raise ValueError('Missing scoring question')
        return rows

    def targets(self):
        rows = loads(self.checked('results/injection_targets.json', results=True))
        targets = {(r['config'], r['id']): r for r in rows}
        if len(targets) != len(rows):
            raise ValueError('Duplicate injection targets')
        return targets

    def image(self, suite, relative):
        if suite not in SUITES:
            raise ValueError('Unknown suite')
        safe_path('.', relative)
        path = f'raw/{suite}/{relative}'
        raw = self.checked(path)
        return raw, hashlib.sha256(raw).hexdigest()

    def download(self, suites, destination):
        """Write a verified raw-only snapshot; no Parquet duplication."""
        destination = Path(destination)
        paths = set()
        for suite in suites:
            paths.add(f'raw/{suite}/data.jsonl')
            for record in self.records(suite):
                for side in ('clean', 'adv'):
                    paths.update(f'raw/{suite}/{p}' for p in record[side].get('images', []))
        result_paths = {'results/injection_targets.json', 'results/model_details.json', 'results/asr.json'}
        manifest = {'version': self.pins['version'], 'files': {}}
        for path in sorted(paths | result_paths):
            raw = self.checked(path, results=path in result_paths)
            dest = safe_path(destination, path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            manifest['files'][path] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        atomic_json(destination / 'MANIFEST.json', manifest)
        atomic_json(destination / 'release.json', self.pins)
        return len(paths | result_paths)
