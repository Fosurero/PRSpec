"""The Besu delivery remains inspectable without credentials or cloud calls."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

from src.report_generator import ReportGenerator, ReportMetadata

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'docs/evidence/2026-11-10/besu-pr5786'


def test_key_free_replay_uses_real_saved_results():
    output = subprocess.check_output(
        [sys.executable, str(ROOT / 'pilot/besu/replay_pr5786.py')], text=True, cwd=ROOT)
    assert 'REPLAY of recorded Meta outputs; no API calls' in output
    assert 'BEFORE 19c989a6 | PARTIAL_MATCH | 1 raw finding(s)' in output
    assert 'AFTER  7605351c | FULL_MATCH | 0 raw finding(s)' in output
    assert 'not a newly discovered bug' in output


def test_focused_manifest_and_recorded_case_are_consistent():
    m = json.loads((E / 'manifest-focused.json').read_text())
    for name in ('before', 'after'):
        d = json.loads((E / f'{name}.json').read_text())
        assert d['besu_commit'] == m['refs'][name]
        assert d['spec_commit'] == m['spec_ref']
        assert d['source_files'] == m['files']
        assert d['meta']['model'] == m['model']
    assert m['verification'] is False


def test_workflow_and_baseline_use_same_model_config():
    workflow = yaml.safe_load((ROOT / 'pilot/besu/workflows/prspec-pilot.yml').read_text())
    steps = workflow['jobs']['analyze']['steps']
    script = next(x['run'] for x in steps if x.get('name', '').startswith('Write the pilot config'))
    inner = script.split("cat > config.yaml <<'CFG'\n", 1)[1].split('\nCFG', 1)[0]
    generated = yaml.safe_load(inner)
    baseline = yaml.safe_load((ROOT / 'pilot/besu/prspec.besu.yaml').read_text())
    assert generated == baseline
    assert generated['llm']['provider'] == 'gemini'
    assert generated['llm']['gemini']['model'] == 'gemini-3.8-flash'
    assert generated['llm']['meta']['model'] == 'muse-wonder-1.0'
    assert workflow['permissions']['pull-requests'] == 'read'
    assert all('comment' not in x.get('name', '').lower() for x in steps)


def test_pilot_report_conversion_uses_one_json_result(tmp_path):
    g = ReportGenerator(str(tmp_path))
    data = json.loads((E / 'before.json').read_text())
    meta = ReportMetadata('EIP-4844 demo', 4844, 'besu', datetime.now(), 'meta')
    raw_path = Path(g.generate_report([data], meta, 'json'))
    payload = json.loads(raw_path.read_text())
    payload['metadata']['timestamp'] = datetime.fromisoformat(payload['metadata']['timestamp'])
    for fmt in ('markdown', 'html'):
        report = Path(g.generate_report(payload['results'], ReportMetadata(**payload['metadata']), fmt))
        assert report.exists()
        assert 'computeExcessBlobGas' in report.read_text()
