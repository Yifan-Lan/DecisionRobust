"""Public CLI. Only the evaluate command instantiates a model adapter."""
import argparse
import json
from pathlib import Path

from .data import Release, SUITES
from .io import read_json


def main():
    parser = argparse.ArgumentParser(prog='decisionrobust')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('download', 'evaluate', 'summarize', 'inspect'):
        p = sub.add_parser(command)
        p.add_argument('--release-dir', help='Local raw release snapshot; omit to use pinned HF files')
        p.add_argument('--cache-dir')
        if command != 'summarize':
            p.add_argument('--pins', help='JSON with immutable release revisions')
            p.add_argument('--suites', nargs='+', choices=SUITES, default=list(SUITES))
        if command == 'download':
            p.add_argument('--output', required=True)
        elif command in ('evaluate', 'summarize'):
            p.add_argument('--output', required=True, help='Local run directory; never commit its contents')
            if command == 'evaluate':
                p.add_argument('--model-config', required=True)
                p.add_argument('--workers', type=int, default=1)
                p.add_argument('--requests-per-second', type=float, default=1.)
                p.add_argument('--attempts', type=int, default=3)
                p.add_argument('--retry-failed', action='store_true')
                p.add_argument('--limit', type=int, help='First N candidates per suite; explicitly a partial evaluation')
    args = parser.parse_args()
    if args.command == 'summarize':
        # Rebuild exactly the recorded selection; do not silently summarize a different panel.
        from .evaluation.runner import prepare, report
        output = Path(args.output)
        manifest = read_json(output / 'run.json')
        binding = manifest['binding']
        release = Release(args.release_dir, binding['release'], args.cache_dir)
        records, _, _ = prepare(release, binding['suites'], binding.get('limit'))
        from .io import digest
        if digest(records) != binding['records_sha256']:
            raise ValueError('Recorded data binding no longer matches')
        # Read-only journal access: repair is confined to the locked evaluation runner.
        from .io import jsonl
        cache = {r['request_key']: r for r in jsonl(output / 'requests.jsonl')}
        result = report(records, cache, output)
    else:
        release = Release(args.release_dir, read_json(args.pins) if args.pins else None, args.cache_dir)
        if args.command == 'download':
            result = {'verified_files': release.download(args.suites, args.output)}
        elif args.command == 'inspect':
            result = {suite: {'candidates': len(release.records(suite)),
                             'originals': len({r['original_id'] for r in release.records(suite)})}
                      for suite in args.suites}
        else:
            from .models import create
            from .evaluation.runner import run
            config = read_json(args.model_config)
            result = run(release, args.suites, create(config), config, args.output,
                         workers=args.workers, requests_per_second=args.requests_per_second,
                         attempts=args.attempts, retry_failed=args.retry_failed, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
