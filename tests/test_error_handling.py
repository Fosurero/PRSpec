"""Tests for error propagation: failures must surface, not be swallowed."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import AnalysisResult, BaseAnalyzer  # noqa: E402
from src.code_fetcher import CodeFetcher  # noqa: E402
from src.config import Config  # noqa: E402
from src.differential import summarize_results  # noqa: E402
from src.engine import scan_path  # noqa: E402
from src.errors import CodeFetchError, ConfigError, SpecFetchError  # noqa: E402
from src.report_generator import ReportGenerator  # noqa: E402
from src.spec_fetcher import SpecFetcher  # noqa: E402
from src.verifier import VerificationEngine  # noqa: E402


class TestCodeFetcherErrors(unittest.TestCase):
    """Fetch failures must never look like source code."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prspec_err_code_")
        self.fetcher = CodeFetcher(cache_dir=self.tmp)

    def test_failed_file_is_reported_not_inlined(self):
        def fake_fetch(owner, repo, path, branch="master", use_cache=True):
            if path.endswith("transaction.go"):
                raise requests.HTTPError("404 Not Found")
            return "package types"

        with patch.object(self.fetcher, "fetch_file", side_effect=fake_fetch):
            outcome = self.fetcher.fetch_eip_files("go-ethereum", 1559)

        self.assertIn("core/types/transaction.go", outcome.failures)
        self.assertNotIn("core/types/transaction.go", outcome.files)
        for content in outcome.files.values():
            self.assertNotIn("Error fetching file", content)

    def test_all_files_failing_raises(self):
        with patch.object(self.fetcher, "fetch_file",
                          side_effect=requests.ConnectionError("no network")):
            with self.assertRaises(CodeFetchError):
                self.fetcher.fetch_eip_files("go-ethereum", 1559)

    def test_connection_errors_are_collected_too(self):
        """Non-HTTP request errors used to escape uncaught."""
        def fake_fetch(owner, repo, path, branch="master", use_cache=True):
            if path.endswith("transaction.go"):
                raise requests.ConnectionError("connection reset")
            return "package types"

        with patch.object(self.fetcher, "fetch_file", side_effect=fake_fetch):
            outcome = self.fetcher.fetch_eip_files("go-ethereum", 1559)

        self.assertIn("core/types/transaction.go", outcome.failures)

    def test_unreadable_cache_falls_back_to_network(self):
        with patch.object(Path, "read_text", side_effect=OSError("permission denied")), \
             patch.object(self.fetcher.session, "get") as mock_get:
            mock_get.return_value = Mock(text="fresh", raise_for_status=Mock())
            cache_file = Path(self.tmp) / "ethereum_go-ethereum_a.go_master"
            cache_file.write_bytes(b"stale")
            content = self.fetcher.fetch_file("ethereum", "go-ethereum", "a.go")

        self.assertEqual(content, "fresh")


class TestSpecFetcherErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prspec_err_spec_")
        self.fetcher = SpecFetcher(cache_dir=self.tmp)

    def test_unfetchable_specs_raise(self):
        with patch.object(self.fetcher, "fetch_eip", return_value="# EIP-1559"), \
             patch.object(self.fetcher, "fetch_execution_spec",
                          side_effect=requests.ConnectionError("no network")):
            with self.assertRaises(SpecFetchError):
                self.fetcher.fetch_eip_spec(1559)

    def test_partial_spec_failure_is_warned_about(self):
        def fake_exec(path, branch="master", use_cache=True):
            if "london" in path:
                raise requests.HTTPError("404")
            return "FORK FILE"

        with patch.object(self.fetcher, "fetch_eip", return_value="# EIP-1559"), \
             patch.object(self.fetcher, "fetch_execution_spec", side_effect=fake_exec):
            result = self.fetcher.fetch_eip_spec(1559)

        self.assertEqual(result["execution_spec"], "FORK FILE")
        self.assertEqual(result["warnings"], [])

    def test_consensus_failure_recorded_as_warning(self):
        with patch.object(self.fetcher, "fetch_eip", return_value="# EIP-4844"), \
             patch.object(self.fetcher, "fetch_execution_spec", return_value="FORK"), \
             patch.object(self.fetcher, "fetch_consensus_spec",
                          side_effect=requests.HTTPError("404")):
            result = self.fetcher.fetch_eip_spec(4844)

        self.assertTrue(result["warnings"])
        self.assertIsNone(result["consensus_spec"])


class _StubAnalyzer(BaseAnalyzer):
    """Concrete analyzer used to exercise the shared parsing helpers."""

    def analyze_compliance(self, spec_text, code_text, context):
        raise NotImplementedError


class TestAnalyzerErrorReporting(unittest.TestCase):
    def test_error_result_carries_error_field(self):
        result = AnalysisResult(status="ERROR", confidence=0, issues=[],
                                summary="boom", error="HTTPError: 500")
        self.assertTrue(result.failed)
        self.assertEqual(result.to_dict()["error"], "HTTPError: 500")

    def test_successful_result_has_no_error_key(self):
        result = AnalysisResult(status="FULL_MATCH", confidence=90,
                                issues=[], summary="ok")
        self.assertFalse(result.failed)
        self.assertNotIn("error", result.to_dict())

    def test_empty_model_response_is_an_error(self):
        with self.assertLogs("src.analyzer", level="ERROR"):
            parsed = _StubAnalyzer()._parse_json_response("")
        self.assertEqual(parsed["status"], "ERROR")
        self.assertIn("error", parsed)

    def test_unparseable_response_is_an_error(self):
        with self.assertLogs("src.analyzer", level="ERROR"):
            parsed = _StubAnalyzer()._parse_json_response("not json at all")
        self.assertEqual(parsed["status"], "ERROR")
        self.assertIn("error", parsed)

    def test_valid_response_still_parses(self):
        payload = json.dumps({"status": "FULL_MATCH", "confidence": 95,
                              "issues": [], "summary": "fine"})
        parsed = _StubAnalyzer()._parse_json_response(payload)
        self.assertEqual(parsed["status"], "FULL_MATCH")


class _ExplodingAnalyzer:
    """Analyzer stub whose every call raises."""

    def _build_refutation_prompt(self, finding, spec_text, context):
        return spec_text

    def analyze_compliance(self, spec_text, code_text, context):
        raise RuntimeError("backend down")


class TestVerifierErrorVisibility(unittest.TestCase):
    def test_failed_round_votes_unsure_and_logs(self):
        engine = VerificationEngine(_ExplodingAnalyzer(), rounds=2)
        with self.assertLogs("src.verifier", level="ERROR"):
            verdict = engine.verify_finding(
                {"spec_reference": "base fee"}, "base fee spec", "code", {}
            )
        self.assertEqual(verdict.votes["unsure"], 2)


class TestSummaryFailureVisibility(unittest.TestCase):
    def test_all_error_results_are_not_uncertain(self):
        results = [{"status": "ERROR", "confidence": 0, "issues": [],
                    "summary": "failed", "file_name": "a.go"}]
        self.assertEqual(summarize_results(results)["overall_status"],
                         "ANALYSIS FAILED")
        gen_summary = ReportGenerator(output_dir=tempfile.mkdtemp())._generate_summary(results)
        self.assertEqual(gen_summary["overall_status"], "ANALYSIS FAILED")
        self.assertEqual(gen_summary["failed_files"], 1)

    def test_partial_failure_keeps_verdict_but_counts_failures(self):
        results = [
            {"status": "ERROR", "confidence": 0, "issues": [], "file_name": "a.go"},
            {"status": "FULL_MATCH", "confidence": 90, "issues": [], "file_name": "b.go"},
        ]
        summary = summarize_results(results)
        self.assertEqual(summary["failed_files"], 1)
        self.assertNotEqual(summary["overall_status"], "ANALYSIS FAILED")


class TestConfigErrors(unittest.TestCase):
    def test_malformed_yaml_raises_config_error(self):
        path = Path(tempfile.mkdtemp()) / "config.yaml"
        path.write_text("llm: [unclosed\n")
        with self.assertRaises(ConfigError):
            Config(str(path))

    def test_non_mapping_config_raises_config_error(self):
        path = Path(tempfile.mkdtemp()) / "config.yaml"
        path.write_text("- just\n- a\n- list\n")
        with self.assertRaises(ConfigError):
            Config(str(path))

    def test_empty_config_falls_back_to_defaults(self):
        path = Path(tempfile.mkdtemp()) / "config.yaml"
        path.write_text("")
        cfg = Config(str(path))
        self.assertEqual(cfg.output_config.get("directory"), "output")


class TestEngineScanErrors(unittest.TestCase):
    def test_unreadable_file_is_reported(self):
        tmp = Path(tempfile.mkdtemp(prefix="prspec_err_engine_"))
        (tmp / "ok.go").write_text("func CalcBaseFee() {}\n")
        (tmp / "bad.go").write_text("func Other() {}\n")

        real_read_text = Path.read_text

        def flaky_read(self, *args, **kwargs):
            if self.name == "bad.go":
                raise OSError("permission denied")
            return real_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", flaky_read):
            result = scan_path(str(tmp))

        self.assertEqual(result["summary"]["files_skipped"], 1)
        self.assertEqual(result["summary"]["files_scanned"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("bad.go", result["errors"][0]["file"])

    def test_clean_scan_reports_no_errors(self):
        tmp = Path(tempfile.mkdtemp(prefix="prspec_err_engine_ok_"))
        (tmp / "ok.go").write_text("func CalcBaseFee() {}\n")
        result = scan_path(str(tmp))
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["summary"]["files_skipped"], 0)


if __name__ == "__main__":
    unittest.main()
