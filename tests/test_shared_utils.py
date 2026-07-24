"""Tests for the shared utilities extracted from duplicated code paths."""

import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.analyzer import BaseAnalyzer, get_analyzer
from src.github_fetcher import CachedGitHubFetcher, raw_url
from src.parser import _brace_delta, _close_block, _find_block_end
from src.summary import summarize_results


class TestCachedGitHubFetcher(unittest.TestCase):
    """The download cache shared by SpecFetcher and CodeFetcher."""

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp(prefix="prspec_fetcher_test_")
        self.fetcher = CachedGitHubFetcher(cache_dir=self.cache_dir)

    def tearDown(self):
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def test_raw_url(self):
        self.assertEqual(
            raw_url("ethereum", "EIPs", "master", "EIPS/eip-1559.md"),
            "https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-1559.md",
        )

    def test_token_sets_authorization_header(self):
        fetcher = CachedGitHubFetcher(github_token="abc", cache_dir=self.cache_dir)
        self.assertEqual(fetcher.session.headers["Authorization"], "token abc")

    @patch("requests.Session.get")
    def test_second_fetch_is_served_from_cache(self, mock_get):
        mock_get.return_value = Mock(text="contents", raise_for_status=Mock())

        first = self.fetcher.fetch_cached("https://example.com/f", "key")
        second = self.fetcher.fetch_cached("https://example.com/f", "key")

        self.assertEqual(first, "contents")
        self.assertEqual(second, "contents")
        self.assertEqual(mock_get.call_count, 1)
        self.assertIn("key", self.fetcher.list_cached_files())

    @patch("requests.Session.get")
    def test_clear_cache_empties_the_directory(self, mock_get):
        mock_get.return_value = Mock(text="contents", raise_for_status=Mock())
        self.fetcher.fetch_cached("https://example.com/f", "key")

        self.fetcher.clear_cache()

        self.assertEqual(self.fetcher.list_cached_files(), [])


class TestBraceHelpers(unittest.TestCase):
    """Brace-block scanning shared by the Go/C#/Java/Rust parsers."""

    def test_brace_delta(self):
        self.assertEqual(_brace_delta("if (x) {"), 1)
        self.assertEqual(_brace_delta("}"), -1)
        self.assertEqual(_brace_delta("x = y;"), 0)

    def test_find_block_end_same_line_open(self):
        lines = ["func f() {", "    body", "}", "after"]
        self.assertEqual(_find_block_end(lines, 0), 2)

    def test_find_block_end_with_lookahead(self):
        lines = ["void F()", "{", "    body", "}", "after"]
        self.assertEqual(_find_block_end(lines, 0, lookahead=3), 3)
        # Without lookahead the brace is never seen, so no block is found.
        self.assertEqual(_find_block_end(lines, 0), 0)

    def test_find_block_end_respects_limit(self):
        lines = ["func f() {", "    body", "}"]
        self.assertEqual(_find_block_end(lines, 0, limit=1), 1)

    def test_close_block_handles_nesting(self):
        lines = ["outer {", "  inner {", "  }", "}", "after"]
        self.assertEqual(_close_block(lines, 0, _brace_delta(lines[0]), len(lines) - 1), 3)


class TestSummarizeResults(unittest.TestCase):
    """Aggregation shared by the report generator and differential engine."""

    RESULTS = [
        {
            "status": "PARTIAL_MATCH",
            "confidence": 80,
            "issues": [
                {"severity": "HIGH", "type": "MISSING_CHECK",
                 "verification": {"verdict": "CONFIRMED"}},
                {"severity": "LOW", "type": "EDGE_CASE",
                 "verification": {"verdict": "REFUTED"}},
            ],
        },
        {"status": "FULL_MATCH", "confidence": 90, "issues": []},
    ]

    def test_core_counts(self):
        s = summarize_results(self.RESULTS)
        self.assertEqual(s["overall_status"], "ISSUES FOUND")
        self.assertEqual(s["average_confidence"], 85)
        self.assertEqual(s["files_analyzed"], 2)
        self.assertEqual(s["total_issues"], 2)
        self.assertEqual(s["high_severity"], 1)
        self.assertEqual(s["low_severity"], 1)
        self.assertNotIn("issue_types", s)
        self.assertNotIn("verification", s)

    def test_optional_breakdowns(self):
        s = summarize_results(self.RESULTS, count_issue_types=True,
                              count_verification=True)
        self.assertEqual(s["issue_types"], {"MISSING_CHECK": 1, "EDGE_CASE": 1})
        self.assertEqual(s["verification"],
                         {"verified": True, "confirmed": 1,
                          "disputed": 0, "refuted": 1})

    def test_confirmed_only_drops_refuted_findings(self):
        s = summarize_results(self.RESULTS, confirmed_only=True)
        self.assertEqual(s["total_issues"], 1)
        self.assertEqual(s["low_severity"], 0)


class _StubAnalyzer(BaseAnalyzer):
    def analyze_compliance(self, spec_text, code_text, context):
        raise NotImplementedError


class TestAnalyzerResultHelpers(unittest.TestCase):
    """Result construction shared by the Gemini/OpenAI/Azure backends."""

    def test_result_from_payload_defaults(self):
        result = _StubAnalyzer()._result_from_payload({}, raw_response="{}")
        self.assertEqual(result.status, "UNCERTAIN")
        self.assertEqual(result.confidence, 0)
        self.assertEqual(result.issues, [])
        self.assertEqual(result.raw_response, "{}")

    def test_error_result(self):
        result = _StubAnalyzer()._error_result("Gemini", ValueError("boom"))
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.summary, "Gemini analysis failed: boom")

    def test_get_analyzer_rejects_unknown_provider(self):
        with self.assertRaises(ValueError):
            get_analyzer("bogus", api_key="k")

    def test_get_analyzer_requires_provider_arguments(self):
        with self.assertRaises(ValueError):
            get_analyzer("azure", api_key="k")


if __name__ == "__main__":
    unittest.main()
