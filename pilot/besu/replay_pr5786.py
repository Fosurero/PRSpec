#!/usr/bin/env python3
"""Replay a real Besu change, or rerun the focused PRSpec analysis live."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/evidence/2026-11-10/besu-pr5786'
MANIFEST = EVIDENCE / 'manifest-focused.json'


def git_show(repo, commit, path):
    return subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{path}'], text=True)


def recorded_results():
    return {name: json.loads((EVIDENCE / f'{name}.json').read_text())
            for name in ('before', 'after')}


def live_results(besu_dir, eips_dir, output):
    # --live intentionally opts in to billable calls and sends public code to Meta.
    sys.path.insert(0, str(ROOT))
    from scripts.mutation_scoreboard import Runner

    manifest = json.loads(MANIFEST.read_text())
    full_spec = git_show(eips_dir, manifest['spec_ref'], 'EIPS/eip-4844.md')
    excerpt = manifest['spec_excerpt']
    if excerpt not in full_spec:
        raise ValueError('Pinned EIP excerpt does not match source; stopping')
    runner = Runner('meta', False, 2, 1)
    runner.analyzer.max_tokens = manifest['max_output_tokens']
    runner.specs[4844] = (excerpt, 'Shard Blob Transactions')
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, commit in manifest['refs'].items():
        code = '\n\n'.join('// SOURCE FILE: ' + f + '\n' + git_show(besu_dir, commit, f)
                           for f in manifest['files'])
        print(f'Analyzing {name} ({commit[:8]}) with {runner.analyzer.model}...', flush=True)
        result = runner.analyze_file(4844, manifest['files'][0], code)
        result.update(besu_commit=commit, spec_commit=manifest['spec_ref'],
                      source_files=manifest['files'])
        (output / f'{name}.json').write_text(json.dumps(result, indent=2) + '\n')
        results[name] = result
        if result['status'] == 'ERROR':
            print('INCOMPLETE: analysis failed; no clean conclusion.', file=sys.stderr)
            break
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live', action='store_true', help='Run two billable Meta API calls')
    p.add_argument('--besu-dir', type=Path, help='Besu Git checkout (required for --live)')
    p.add_argument('--eips-dir', type=Path, help='EIPs Git checkout (required for --live)')
    p.add_argument('--out', type=Path, default=ROOT / 'output/besu-pr5786-rerun')
    args = p.parse_args()
    if args.live and (not args.besu_dir or not args.eips_dir):
        p.error('--live requires --besu-dir and --eips-dir')
    print('PRSpec × Besu | Historical PR #5786 | EIP-4844')
    print('A real, published historical fix; not a newly discovered bug.')
    print('Mode:', 'LIVE Meta calls' if args.live else 'REPLAY of recorded Meta outputs; no API calls')
    print('\n--- Actual change made by Besu ---')
    print((EVIDENCE / 'real-change.diff').read_text())
    try:
        results = (live_results(args.besu_dir, args.eips_dir, args.out) if args.live
                   else recorded_results())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'INCOMPLETE: {type(exc).__name__}; no clean conclusion.', file=sys.stderr)
        return 20
    print('\n--- PRSpec output (focused rule, three source files) ---')
    for name in ('before', 'after'):
        if name not in results:
            return 20
        result = results[name]
        print(f"{name.upper():6} {result['besu_commit'][:8]} | {result['status']} | {len(result.get('issues', []))} raw finding(s)")
        for issue in result.get('issues', []):
            print('  Location:', issue.get('code_location', 'unknown'))
            print('  Finding:', issue.get('description', ''))
            print('  Spec:', issue.get('spec_reference', ''))
            print('  Suggested fix:', issue.get('suggestion', ''))
    print('\nNo verifier was run. A matching report is not proof of full compliance.')
    print('This targeted experiment combines three files; the draft CI workflow does not yet do this.')
    return 20 if any(r.get('status') == 'ERROR' for r in results.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
