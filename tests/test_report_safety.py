"""Reports must not hide incomplete analysis or render untrusted HTML."""
from datetime import datetime
from pathlib import Path

from src.report_generator import ReportGenerator, ReportMetadata


def test_incomplete_does_not_say_clean(tmp_path):
    generator = ReportGenerator(str(tmp_path))
    results = [{'file_name': 'example.java', 'status': 'ERROR', 'confidence': 0,
                'issues': [], 'summary': 'provider failed'}]
    meta = ReportMetadata('test', 4844, 'besu', datetime.now(), 'model')
    assert generator._generate_summary(results)['overall_status'] == 'INCOMPLETE'
    report = Path(generator.generate_report(results, meta, 'html')).read_text()
    assert 'Analysis incomplete' in report
    assert 'No compliance issues were detected' not in report
    markdown = Path(generator.generate_report(results, meta, 'markdown')).read_text()
    assert 'Analysis incomplete; no clean conclusion.' in markdown
    assert 'No issues found in this file.' not in markdown


def test_html_escapes_untrusted_result_fields(tmp_path):
    generator = ReportGenerator(str(tmp_path))
    payload = '<script>alert(1)</script>'
    results = [{'file_name': payload, 'status': 'PARTIAL_MATCH', 'confidence': 70,
                'issues': [], 'summary': payload}]
    meta = ReportMetadata(payload, 4844, 'besu', datetime.now(), 'model')
    report = Path(generator.generate_report(results, meta, 'html')).read_text()
    assert payload not in report
    assert '&lt;script&gt;' in report


def test_full_match_does_not_claim_compliance(tmp_path):
    generator = ReportGenerator(str(tmp_path))
    result = {'file_name': 'x', 'status': 'FULL_MATCH', 'confidence': 90, 'issues': []}
    assert generator._generate_summary([result])['overall_status'] == 'NO FINDINGS'
