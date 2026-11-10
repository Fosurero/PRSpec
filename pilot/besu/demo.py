#!/usr/bin/env python3
"""Besu pilot: reproduce an injected patch, replay recorded Meta review, check a constant."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/evidence/2026-11-10'
SCORE = EVIDENCE / 'meta-live/scoreboard'


def title(text):
    print('\n' + '=' * 72 + '\n' + text + '\n' + '=' * 72, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--besu-dir', required=True, type=Path)
    parser.add_argument('--eips-dir', required=True, type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'output/besu-case-demo')
    args = parser.parse_args()
    title('1. Reproduce two intentional mutations (no client files modified)')
    cmd = [sys.executable, str(ROOT / 'scripts/mutation_scoreboard.py'), '--besu-dir', str(args.besu_dir), '--eips-dir', str(args.eips_dir), '--only', 'M2,M5', '--dry-run', '--out', str(args.out)]
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode:
        return result.returncode
    fresh = (args.out / 'patches/M5.diff').read_text()
    recorded = (EVIDENCE / 'scoreboard-dry-run/patches/M5.diff').read_text()
    if fresh != recorded:
        print('ERROR: fresh patch differs from recorded Meta case; refusing replay.', file=sys.stderr)
        return 1
    title('2. Injected M5: what if the Taylor-series index starts at 2?')
    print(fresh)
    title('3. Recorded Meta review (REPLAY, not a live model call)')
    result_data = json.loads((SCORE / 'raw/run1-M5-BlobFeeMarket.json').read_text())
    score = json.loads((SCORE / 'scoreboard.json').read_text())
    row = next(row for row in score['rows'] if row['id'] == 'M5')
    issue = next(i for i in result_data['issues'] if i.get('verification', {}).get('verdict') == 'CONFIRMED')
    print('Model:', result_data['meta']['model_version'])
    print('Location:', issue['code_location'])
    print('Rule excerpt:')
    print(issue['spec_reference'])
    print('\nModel finding:', issue['description'])
    print('Suggested fix:', issue['suggestion'])
    print('Automated review:', issue['verification']['verdict'], '(2 model-review rounds; not independent proof)')
    print('Scoreboard outcome:', row['outcome'])
    title('4. M2: a fresh, deterministic check with no model')
    m2 = json.loads((args.out / 'witness.json').read_text())['M2']
    for rule in m2['rules']:
        print(f"{rule['rule_id']}: expected {rule['expected']}, found {rule['actual']} at {rule['code_file']}:{rule['code_line']}")
        print('Spec line:', rule['spec_line'], '| outcome:', rule['status'])
    print('\nM5 and M2 are intentional mutations, NOT real Besu defects. No model calls in this walkthrough.')
    print('M5 replay is recorded model output; verification is automated and requires human review.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
