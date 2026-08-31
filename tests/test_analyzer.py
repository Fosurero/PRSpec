"""Tests for prompt building, response parsing, and the Gemini/OpenAI backends."""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import (
    AnalysisResult,
    AzureAIAnalyzer,
    BaseAnalyzer,
    GeminiAnalyzer,
    OpenAIAnalyzer,
    get_analyzer,
)

_CONTEXT = {
    "eip_number": 1559,
    "eip_title": "EIP-1559: Fee market change",
    "file_name": "eip1559.go",
    "function_name": "CalcBaseFee",
    "language": "go",
    "focus_areas": ["base_fee_calculation"],
}

_RESPONSE_OBJ = {
    "status": "PARTIAL_MATCH",
    "confidence": 75,
    "issues": [{"severity": "HIGH", "description": "fee not burned"}],
    "summary": "One deviation found.",
}


class _Analyzer(BaseAnalyzer):
    """Concrete BaseAnalyzer that records what it was asked to analyze."""

    def __init__(self):
        self.calls = []

    def analyze_compliance(self, spec_text, code_text, context):
        self.calls.append((spec_text, code_text, context))
        return AnalysisResult("FULL_MATCH", 100, [], "ok")


class TestAnalysisResult(unittest.TestCase):
    def test_to_dict_omits_raw_response(self):
        result = AnalysisResult("FULL_MATCH", 90, [], "ok", raw_response="{...}")
        self.assertEqual(set(result.to_dict()),
                         {"status", "confidence", "issues", "summary"})

    def test_has_issues(self):
        self.assertFalse(AnalysisResult("FULL_MATCH", 90, [], "ok").has_issues)
        self.assertTrue(AnalysisResult("MISSING", 60, [{}], "ok").has_issues)

    def test_high_severity_issues_filtered(self):
        result = AnalysisResult("MISSING", 60, [
            {"severity": "HIGH"}, {"severity": "LOW"},
        ], "ok")
        self.assertEqual(len(result.high_severity_issues), 1)


class TestPrompts(unittest.TestCase):
    def setUp(self):
        self.analyzer = _Analyzer()

    def test_analysis_prompt_uses_eip_title(self):
        prompt = self.analyzer._build_analysis_prompt("SPEC", "CODE", _CONTEXT)
        self.assertIn("EIP-1559: Fee market change", prompt)
        self.assertIn("SPEC", prompt)
        self.assertIn("CODE", prompt)
        self.assertIn("eip1559.go", prompt)
        self.assertIn("base_fee_calculation", prompt)

    def test_analysis_prompt_falls_back_to_eip_number(self):
        prompt = self.analyzer._build_analysis_prompt(
            "SPEC", "CODE", {"eip_number": 4844})
        self.assertIn("EIP-4844", prompt)

    def test_analysis_prompt_without_any_eip_context(self):
        prompt = self.analyzer._build_analysis_prompt("SPEC", "CODE", {})
        self.assertIn("the Ethereum specification", prompt)
        self.assertIn("EIP: unknown", prompt)

    def test_analyze_multiple_files_concatenates_with_headers(self):
        self.analyzer.analyze_multiple_files(
            "SPEC", {"a.go": "AAA", "b.go": "BBB"}, _CONTEXT)
        combined = self.analyzer.calls[0][1]
        self.assertIn("=== FILE: a.go ===\nAAA", combined)
        self.assertIn("=== FILE: b.go ===\nBBB", combined)

    def test_refutation_prompt_embeds_the_claim(self):
        prompt = self.analyzer._build_refutation_prompt({
            "type": "DEVIATION", "severity": "HIGH",
            "description": "fee not burned",
            "spec_reference": "the base fee MUST be burned",
            "code_location": "CalcBaseFee",
        }, "SPEC TEXT", _CONTEXT)
        self.assertTrue(prompt.startswith("SPEC TEXT"))
        self.assertIn("INDEPENDENT VERIFICATION TASK", prompt)
        self.assertIn("fee not burned", prompt)
        self.assertIn("CalcBaseFee", prompt)

    def test_refutation_prompt_tolerates_a_sparse_finding(self):
        prompt = self.analyzer._build_refutation_prompt({}, "SPEC", _CONTEXT)
        self.assertIn("type: UNKNOWN", prompt)


class TestResponseParsing(unittest.TestCase):
    def setUp(self):
        self.parse = _Analyzer()._parse_json_response

    def test_plain_json(self):
        self.assertEqual(self.parse(json.dumps(_RESPONSE_OBJ)), _RESPONSE_OBJ)

    def test_json_in_markdown_fence(self):
        text = f"```json\n{json.dumps(_RESPONSE_OBJ)}\n```"
        self.assertEqual(self.parse(text), _RESPONSE_OBJ)

    def test_json_in_bare_fence(self):
        text = f"```\n{json.dumps(_RESPONSE_OBJ)}\n```"
        self.assertEqual(self.parse(text), _RESPONSE_OBJ)

    def test_json_wrapped_in_prose(self):
        text = f"Here is my analysis:\n{json.dumps(_RESPONSE_OBJ)}\nHope that helps!"
        self.assertEqual(self.parse(text), _RESPONSE_OBJ)

    def test_truncated_object_is_repaired(self):
        text = '{"status": "PARTIAL_MATCH", "confidence": 70'
        self.assertEqual(self.parse(text)["confidence"], 70)

    def test_truncated_issue_list_is_repaired(self):
        text = ('{"status": "MISSING", "issues": [{"severity": "HIGH", '
                '"description": "fee not burned')
        parsed = self.parse(text)
        self.assertEqual(parsed["status"], "MISSING")
        self.assertEqual(parsed["issues"][0]["severity"], "HIGH")

    def test_trailing_garbage_after_valid_object(self):
        text = '{"status": "FULL_MATCH"} trailing tokens {'
        self.assertEqual(self.parse(text)["status"], "FULL_MATCH")

    def test_unparseable_response_yields_error_result(self):
        parsed = self.parse("the model refused to answer")
        self.assertEqual(parsed["status"], "ERROR")
        self.assertEqual(parsed["confidence"], 0)
        self.assertIn("Failed to parse response", parsed["summary"])


class TestGeminiAnalyzer(unittest.TestCase):
    def _analyzer(self, response_text):
        client = mock.MagicMock()
        client.models.generate_content.return_value = mock.MagicMock(text=response_text)
        with mock.patch("google.genai.Client", return_value=client):
            analyzer = GeminiAnalyzer(api_key="k", model="gemini-test",
                                      max_output_tokens=100, temperature=0.5)
        return analyzer, client

    def test_successful_analysis(self):
        analyzer, client = self._analyzer(json.dumps(_RESPONSE_OBJ))
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "PARTIAL_MATCH")
        self.assertEqual(result.confidence, 75)
        self.assertEqual(client.models.generate_content.call_args.kwargs["model"],
                         "gemini-test")

    def test_missing_fields_fall_back_to_defaults(self):
        analyzer, _ = self._analyzer("{}")
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "UNCERTAIN")
        self.assertEqual(result.confidence, 0)

    def test_api_error_returns_error_result(self):
        analyzer, client = self._analyzer("{}")
        client.models.generate_content.side_effect = RuntimeError("quota exceeded")
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "ERROR")
        self.assertIn("quota exceeded", result.summary)

    def test_get_model_info(self):
        analyzer, _ = self._analyzer("{}")
        info = analyzer.get_model_info()
        self.assertEqual(info["provider"], "gemini")
        self.assertEqual(info["max_output_tokens"], 100)

    def test_missing_dependency_raises_import_error(self):
        with mock.patch.dict(sys.modules, {"google.genai": None}):
            with self.assertRaises(ImportError):
                GeminiAnalyzer(api_key="k")


class TestOpenAIAnalyzer(unittest.TestCase):
    def _analyzer(self, response_text):
        client = mock.MagicMock()
        client.chat.completions.create.return_value = mock.MagicMock(
            choices=[mock.MagicMock(message=mock.MagicMock(content=response_text))])
        with mock.patch("openai.OpenAI", return_value=client):
            analyzer = OpenAIAnalyzer(api_key="k", model="gpt-test",
                                      max_tokens=50, temperature=0.4)
        return analyzer, client

    def test_successful_analysis(self):
        analyzer, client = self._analyzer(json.dumps(_RESPONSE_OBJ))
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "PARTIAL_MATCH")
        sent = client.chat.completions.create.call_args.kwargs
        self.assertEqual(sent["model"], "gpt-test")
        self.assertEqual(sent["max_tokens"], 50)
        self.assertEqual(sent["messages"][0]["role"], "system")

    def test_api_error_returns_error_result(self):
        analyzer, client = self._analyzer("{}")
        client.chat.completions.create.side_effect = RuntimeError("rate limited")
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "ERROR")
        self.assertIn("rate limited", result.summary)

    def test_get_model_info(self):
        analyzer, _ = self._analyzer("{}")
        self.assertEqual(analyzer.get_model_info()["provider"], "openai")

    def test_missing_dependency_raises_import_error(self):
        with mock.patch.dict(sys.modules, {"openai": None}):
            with self.assertRaises(ImportError):
                OpenAIAnalyzer(api_key="k")


class _RetryResponse:
    def __init__(self, status_code, headers=None, payload=None):
        self.status_code = status_code
        self.reason = "Too Many Requests"
        self.headers = headers or {}
        self._payload = payload or {"content": [{"type": "text", "text": "{}"}]}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)


class TestAzureRetry(unittest.TestCase):
    """Rate-limited Foundry deployments must be retried, not dropped."""

    def _analyzer(self, responses, max_retries=2):
        analyzer = AzureAIAnalyzer(api_key="k", endpoint="https://x/v1",
                                   model="claude", max_retries=max_retries)
        analyzer.session = mock.MagicMock()
        analyzer.session.post.side_effect = responses
        return analyzer

    def test_retries_then_succeeds(self):
        ok = _RetryResponse(200, payload={"content": [
            {"type": "text", "text": json.dumps(_RESPONSE_OBJ)}]})
        analyzer = self._analyzer([_RetryResponse(429), _RetryResponse(529), ok])
        with mock.patch("src.analyzer.time.sleep") as sleep:
            result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "PARTIAL_MATCH")
        self.assertEqual(analyzer.session.post.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1.0, 2.0])

    def test_honors_retry_after_header(self):
        ok = _RetryResponse(200)
        analyzer = self._analyzer([_RetryResponse(429, {"Retry-After": "7"}), ok])
        with mock.patch("src.analyzer.time.sleep") as sleep:
            analyzer.analyze_compliance("spec", "code", _CONTEXT)
        sleep.assert_called_once_with(7.0)

    def test_non_numeric_retry_after_falls_back_to_backoff(self):
        ok = _RetryResponse(200)
        analyzer = self._analyzer(
            [_RetryResponse(429, {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}), ok])
        with mock.patch("src.analyzer.time.sleep") as sleep:
            analyzer.analyze_compliance("spec", "code", _CONTEXT)
        sleep.assert_called_once_with(1.0)

    def test_exhausted_retries_produce_error_result(self):
        analyzer = self._analyzer([_RetryResponse(429)] * 3, max_retries=2)
        with mock.patch("src.analyzer.time.sleep"):
            result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "ERROR")
        self.assertIn("429", result.summary)
        self.assertEqual(analyzer.session.post.call_count, 3)

    def test_only_text_blocks_are_concatenated(self):
        payload = {"content": [
            {"type": "thinking", "thinking": "hmm"},
            {"type": "text", "text": json.dumps(_RESPONSE_OBJ)},
        ]}
        analyzer = self._analyzer([_RetryResponse(200, payload=payload)])
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "PARTIAL_MATCH")


class TestGetAnalyzerFactory(unittest.TestCase):
    def test_builds_gemini(self):
        with mock.patch("google.genai.Client"):
            self.assertIsInstance(get_analyzer("GEMINI", api_key="k"), GeminiAnalyzer)

    def test_gemini_requires_api_key(self):
        with self.assertRaises(ValueError):
            get_analyzer("gemini")

    def test_builds_openai(self):
        with mock.patch("openai.OpenAI"):
            self.assertIsInstance(get_analyzer("openai", api_key="k"), OpenAIAnalyzer)

    def test_openai_requires_api_key(self):
        with self.assertRaises(ValueError):
            get_analyzer("openai")

    def test_unknown_provider(self):
        with self.assertRaises(ValueError):
            get_analyzer("llama")


if __name__ == "__main__":
    unittest.main()
