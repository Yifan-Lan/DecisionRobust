"""Keep documentation, configs and an unpacked source release usable together."""
import contextlib
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from audit_public_tree import audit, candidate_files
from decisionrobust import __version__
from decisionrobust.cli import main
from decisionrobust.evaluation.runner import prepare


class ReleaseConsistencyTests(unittest.TestCase):
    def test_markdown_links_and_shell_syntax(self):
        for path in [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md'))]:
            text = path.read_text()
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if '://' in target or target.startswith('#'):
                    continue
                target = unquote(target.split('#')[0].split('?')[0])
                self.assertTrue((path.parent / target).exists(), (path.name, target))
            for block in re.findall(r'```bash\n(.*?)```', text, re.S):
                result = subprocess.run(['bash', '-n'], input=block, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, (path.name, result.stderr))

    def test_summary_rejects_ignored_overrides(self):
        for option in ('--pins', '--suites'):
            with patch.object(sys, 'argv', ['decisionrobust', 'summarize', '--output', 'unused', option, 'unused']):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                    main()
            self.assertEqual(result.exception.code, 2)

    def test_repeated_suite_is_not_double_counted(self):
        # Selection must fail before touching any release files or invoking a model.
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            prepare(None, ['text_adversarial_curated'] * 2)

    def test_source_archive_scan_after_tests(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'README.md').write_text('Example source tree')
            for directory in ('__pycache__', 'runs', 'build', 'sample.egg-info', 'website/data'):
                target = root / directory
                target.mkdir(parents=True)
                (target / 'generated.txt').write_text('generated')
            self.assertEqual(candidate_files(root), ['README.md'])
            self.assertFalse(audit(root, candidate_files(root))['findings'])
            # Source credentials must still be rejected, even without Git metadata.
            (root / '.env').write_text('')
            self.assertIn('.env', candidate_files(root))
            self.assertTrue(audit(root, candidate_files(root))['findings'])
            # An explicit packaging list cannot bypass prohibited generated paths.
            self.assertTrue(audit(root, ['runs/generated.txt'])['findings'])

    def test_custom_adapter_from_installed_style_launcher(self):
        # Mimic a console script whose sys.path[0] is a bin dir, not the repo root.
        code = '''
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != root]
sys.path.insert(0, str(root / 'src'))
from decisionrobust.models import create
from decisionrobust.models.base import UnsupportedInput
adapter = create(json.loads((root / 'configs/models/custom.json').read_text()))
try:
    adapter.predict({'state': 'test', 'questions': {}}, [])
except UnsupportedInput:
    print('contract-loaded')
else:
    raise RuntimeError('The example must not invent predictions')
'''
        result = subprocess.run([sys.executable, '-c', code, str(ROOT)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('contract-loaded', result.stdout)

    def test_reference_results_and_code_version(self):
        manifest = json.loads((ROOT / 'results/manifest.json').read_text())
        pins = json.loads((ROOT / 'site_config.json').read_text())
        self.assertEqual(manifest['release'], pins)
        for name, metadata in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ROOT / 'results' / name).read_bytes()).hexdigest(), metadata['sha256'])
        self.assertIn(f'version = "{__version__}"', (ROOT / 'pyproject.toml').read_text())
        self.assertEqual(json.loads((ROOT / 'submissions/template/manifest.json').read_text())['release'],
                         {k: pins[k] for k in ('version', 'data_revision', 'results_revision')})


if __name__ == '__main__':
    unittest.main()
