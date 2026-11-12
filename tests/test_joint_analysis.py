"""Joint analysis, source safety and workflow coverage (no network/model calls)."""
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from src.analyzer import AnalysisResult
from src.cli import _exit_code, _run_analysis, _run_outcome
from src.code_fetcher import CodeFetcher, FetchError

ROOT = Path(__file__).resolve().parents[1]
FILES = CodeFetcher.CLIENTS['besu']['eip_files'][4844]


def run_joint(tmp_path, files, missing=None, verify=False, **kw):
    spec = tmp_path / 'spec.md'
    spec.write_text('Pinned specification')
    fetcher = Mock(last_fetch_errors=missing or {})
    fetcher.fetch_eip_implementation.return_value = files
    analyzer = Mock()
    analyzer.analyze_compliance.return_value = AnalysisResult(
        status='FULL_MATCH', confidence=70, issues=[], summary='done')
    cfg = Mock(github_token=None)
    cfg.get_eip_focus_areas.return_value = []
    with patch('src.cli.CodeFetcher', return_value=fetcher) as cls, \
         patch('src.cli._build_analyzer', return_value=analyzer), \
         patch('src.cli.SpecFetcher') as spec_fetcher:
        cls.client_language.return_value = 'java'
        result, _ = _run_analysis(4844, 'besu', cfg, 'meta',
                                  spec_file=str(spec), multi_file=True, verify=verify, **kw)
        spec_fetcher.return_value.fetch_eip_spec.assert_not_called()
    return result[0], analyzer


def test_joint_sends_all_labeled_sources_and_hashes(tmp_path):
    files = {FILES[0]: 'class A {}', FILES[1]: 'class B {}'}
    result, analyzer = run_joint(tmp_path, files)
    analyzer.analyze_compliance.assert_called_once()
    spec, combined, _ = analyzer.analyze_compliance.call_args.args
    assert spec == 'Pinned specification'
    for path, content in files.items():
        assert f'=== FILE: {path} ===\n{content}' in combined
        assert result['source_sha256'][path] == hashlib.sha256(content.encode()).hexdigest()
    assert result['source_files'] == list(files)
    assert result['spec_sha256'] == hashlib.sha256(spec.encode()).hexdigest()
    assert result['status'] == 'FULL_MATCH'


def test_incomplete_joint_never_calls_model(tmp_path):
    result, analyzer = run_joint(tmp_path, {FILES[0]: 'class A {}'}, {FILES[1]: 'not found'})
    analyzer.analyze_compliance.assert_not_called()
    assert result['status'] == 'ERROR'
    assert _exit_code(_run_outcome([result], False), 'incomplete') == 20
    assert FILES[1] in result['source_errors']


def test_oversized_joint_never_calls_model(tmp_path):
    result, analyzer = run_joint(tmp_path, {FILES[0]: 'x' * 160_001})
    analyzer.analyze_compliance.assert_not_called()
    assert result['status'] == 'ERROR'


def test_raw_response_is_retained():
    result = AnalysisResult('FULL_MATCH', 90, [], 'done', raw_response='{"status":"FULL_MATCH"}')
    assert result.to_dict()['raw_response'] == '{"status":"FULL_MATCH"}'


def test_verifier_receives_joint_context(tmp_path):
    files = {FILES[0]: 'class A {}', FILES[1]: 'class B {}'}
    with patch('src.verifier.VerificationEngine') as engine:
        result, _ = run_joint(tmp_path, files, verify=True)
    args = engine.return_value.verify_results.call_args.args
    assert args[0] == [result]
    combined = args[2]['Multi-file context']
    assert all(f'=== FILE: {p} ===\n{c}' in combined for p, c in files.items())


def test_selected_files_must_be_registered_and_unique(tmp_path):
    f = CodeFetcher(cache_dir=str(tmp_path / 'cache'))
    for paths in [['../../etc/passwd'], [FILES[0], FILES[0]]]:
        with pytest.raises(ValueError):
            f.fetch_eip_implementation('besu', 4844, selected_files=paths)


def test_symlink_source_never_read(tmp_path):
    root = tmp_path / 'repo'
    path = root / FILES[0]
    path.parent.mkdir(parents=True)
    secret = tmp_path / 'secret'
    secret.write_text('do not send')
    path.symlink_to(secret)
    f = CodeFetcher(cache_dir=str(tmp_path / 'cache'))
    with pytest.raises(FetchError) as exc:
        f.fetch_eip_implementation('besu', 4844, source_dir=str(root), selected_files=[FILES[0]])
    assert 'symlink' in str(exc.value)
    assert 'do not send' not in str(exc.value)


def test_workflow_covers_blockcreator_and_uses_pinned_joint_mode():
    trigger = yaml.safe_load((ROOT / 'pilot/besu/workflows/prspec-pilot-trigger.yml').read_text())
    workflow = yaml.safe_load((ROOT / 'pilot/besu/workflows/prspec-pilot.yml').read_text())
    paths = trigger.get('on', trigger.get(True))['pull_request']['paths']
    assert FILES[0] in paths
    steps = workflow['jobs']['analyze']['steps']
    checkout = next(s for s in steps if s.get('name', '').startswith('Check out PR files'))
    assert 'ethereum/blockcreation/src/main/java' in checkout['with']['sparse-checkout']
    eips = next(s for s in steps if s.get('name', '').startswith('Check out pinned EIP'))
    assert eips['with']['ref'] == 'eb2e7a97aa70b1d7f39968c6be9ed3e731512f9d'
    run = next(s['run'] for s in steps if s.get('name', '').startswith('Run PRSpec'))
    assert '--multi-file' in run and '--spec-file' in run and '--no-verify' in run


def test_context_callback_runs_before_model_call(tmp_path):
    order = []
    files = {FILES[0]: 'class A {}', FILES[1]: 'class B {}'}

    def callback(code_files, spec_text, errors, combined_bytes):
        order.append(('context', sorted(code_files), dict(errors), combined_bytes > 0))

    result, analyzer = run_joint(tmp_path, files, context_callback=callback)
    analyzer.analyze_compliance.assert_called_once()
    assert order == [('context', sorted(files), {}, True)]
    # The callback fires before the request: an incomplete context never reaches the model.
    order.clear()
    result, analyzer = run_joint(tmp_path, {FILES[0]: 'class A {}'}, {FILES[1]: 'missing'},
                                 context_callback=callback)
    assert order and order[0][2] == {FILES[1]: 'missing'}
    analyzer.analyze_compliance.assert_not_called()


def test_multiple_output_formats_come_from_one_analysis(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from src.cli import cli
    monkeypatch.chdir(tmp_path)
    analyzer = Mock()
    analyzer.get_model_info.return_value = {'model': 'fake-model'}
    results = [{'file_name': 'Multi-file context', 'status': 'FULL_MATCH', 'confidence': 70,
                'issues': [], 'summary': 'ok', 'source_files': [FILES[0]],
                'client_ref': 'a' * 40, 'spec_sha256': 'b' * 64,
                'meta': {'prompt_token_count': 10, 'candidates_token_count': 2}}]
    with patch('src.cli._run_analysis', return_value=(results, analyzer)) as run:
        out = CliRunner().invoke(cli, ['analyze', '--eip', '4844', '--client', 'besu',
                                       '--provider', 'gemini', '--multi-file',
                                       '--output', 'json,markdown,html'])
    assert out.exit_code == 0, out.output
    run.assert_called_once()
    assert sorted(p.suffix for p in (tmp_path / 'output').iterdir()) == ['.html', '.json', '.md']
    md = next((tmp_path / 'output').glob('*.md')).read_text()
    assert 'a' * 40 in md and 'input 10' in md


def test_unknown_output_format_is_rejected_before_analysis(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from src.cli import cli
    monkeypatch.chdir(tmp_path)
    with patch('src.cli._run_analysis') as run:
        out = CliRunner().invoke(cli, ['analyze', '--eip', '4844', '--client', 'besu',
                                       '--output', 'json,pdf'])
    assert out.exit_code != 0
    run.assert_not_called()


def test_workflow_prefers_gemini_falls_back_to_meta_and_scopes_secrets():
    workflow = yaml.safe_load((ROOT / 'pilot/besu/workflows/prspec-pilot.yml').read_text())
    models = workflow['env']['PRSPEC_MODELS'].split()
    assert models[0] == 'gemini:gemini-3.8-flash' and models[-1] == 'meta:muse-wonder-1.0'
    job = workflow['jobs']['analyze']
    assert job['continue-on-error'] is True
    assert set(workflow['permissions'].values()) == {'read'}
    run_step = next(s for s in job['steps'] if s.get('name', '').startswith('Run PRSpec'))
    assert {'GEMINI_API_KEY', 'MODEL_API_KEY'} <= set(run_step['env'])
    assert '--output json,markdown,html' in run_step['run'] and 'attempts.tsv' in run_step['run']
    for step in job['steps']:
        if step is not run_step:
            assert 'secrets.' not in yaml.safe_dump(step)
