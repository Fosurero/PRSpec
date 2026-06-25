"""Tests for the Azure AI Foundry analyzer (Anthropic Messages deployments)."""

import json
import sys
import unittest
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import AzureAIAnalyzer, get_analyzer


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _FakeSession:
    """Stand-in for requests.Session that records the last POST."""

    def __init__(self, response):
        self._response = response
        self.last = {}

    def post(self, url, json=None, headers=None, timeout=None):
        self.last = {"url": url, "json": json, "headers": headers, "timeout": timeout}
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _messages_payload(obj):
    """Wrap a JSON object the way the Anthropic Messages API returns text."""
    return {
        "content": [{"type": "text", "text": json.dumps(obj)}],
        "stop_reason": "end_turn",
    }


def _analyzer(session, **overrides):
    kwargs = dict(
        api_key="secret",
        endpoint="https://x.services.ai.azure.com/anthropic/v1/messages",
        model="claude-opus-4-8",
    )
    kwargs.update(overrides)
    analyzer = AzureAIAnalyzer(**kwargs)
    analyzer.session = session
    return analyzer


_CONTEXT = {"eip_number": 1559, "eip_title": "EIP-1559", "language": "csharp"}


class TestAzureAIAnalyzer(unittest.TestCase):
    def test_full_match_is_parsed(self):
        payload = _messages_payload({
            "status": "FULL_MATCH", "confidence": 95, "issues": [],
            "summary": "Implementation matches the spec.",
        })
        analyzer = _analyzer(_FakeSession(_FakeResponse(payload=payload)))
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)

        self.assertEqual(result.status, "FULL_MATCH")
        self.assertEqual(result.confidence, 95)
        self.assertFalse(result.has_issues)

    def test_issues_are_parsed(self):
        payload = _messages_payload({
            "status": "MISSING", "confidence": 70,
            "issues": [{
                "type": "MISSING_CHECK", "severity": "HIGH",
                "spec_reference": "base fee must be burned",
                "description": "fee not burned",
            }],
            "summary": "Found one deviation.",
        })
        analyzer = _analyzer(_FakeSession(_FakeResponse(payload=payload)))
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)

        self.assertEqual(result.status, "MISSING")
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.high_severity_issues[0]["severity"], "HIGH")

    def test_request_shape_and_auth(self):
        session = _FakeSession(_FakeResponse(payload=_messages_payload(
            {"status": "FULL_MATCH", "issues": []})))
        analyzer = _analyzer(session)
        analyzer.analyze_compliance("spec", "code", _CONTEXT)

        sent = session.last
        # Bearer auth + the Anthropic version header, posted to the messages URL.
        self.assertEqual(sent["url"], "https://x.services.ai.azure.com/anthropic/v1/messages")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(sent["headers"]["anthropic-version"], "2023-06-01")
        # Messages request body, not OpenAI chat-completions.
        self.assertEqual(sent["json"]["model"], "claude-opus-4-8")
        self.assertIn("max_tokens", sent["json"])
        self.assertEqual(sent["json"]["messages"][0]["role"], "user")
        self.assertIn("system", sent["json"])
        # temperature is omitted by default (Opus 4.x rejects it).
        self.assertNotIn("temperature", sent["json"])

    def test_temperature_sent_only_when_set(self):
        session = _FakeSession(_FakeResponse(payload=_messages_payload(
            {"status": "FULL_MATCH", "issues": []})))
        analyzer = _analyzer(session, temperature=0.2)
        analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(session.last["json"]["temperature"], 0.2)

    def test_custom_anthropic_version(self):
        session = _FakeSession(_FakeResponse(payload=_messages_payload(
            {"status": "FULL_MATCH", "issues": []})))
        analyzer = _analyzer(session, anthropic_version="2024-10-01")
        analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(session.last["headers"]["anthropic-version"], "2024-10-01")

    def test_http_error_returns_error_status(self):
        analyzer = _analyzer(_FakeSession(_FakeResponse(status_code=401)))
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "ERROR")
        self.assertIn("Azure AI analysis failed", result.summary)

    def test_network_error_returns_error_status(self):
        analyzer = _analyzer(_FakeSession(requests.ConnectionError("boom")))
        result = analyzer.analyze_compliance("spec", "code", _CONTEXT)
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.confidence, 0)

    def test_missing_endpoint_raises(self):
        with self.assertRaises(ValueError):
            AzureAIAnalyzer(api_key="k", endpoint="", model="claude-opus-4-8")

    def test_missing_deployment_raises(self):
        with self.assertRaises(ValueError):
            AzureAIAnalyzer(api_key="k", endpoint="https://x", model="")

    def test_get_model_info(self):
        analyzer = AzureAIAnalyzer(
            api_key="k", endpoint="https://x/anthropic/v1/messages",
            model="claude-opus-4-8",
        )
        info = analyzer.get_model_info()
        self.assertEqual(info["provider"], "azure")
        self.assertEqual(info["model"], "claude-opus-4-8")


class TestFactory(unittest.TestCase):
    def test_factory_builds_azure(self):
        analyzer = get_analyzer(
            "azure", api_key="k",
            endpoint="https://x.services.ai.azure.com/anthropic/v1/messages",
            model="claude-opus-4-8",
        )
        self.assertIsInstance(analyzer, AzureAIAnalyzer)

    def test_factory_azure_requires_endpoint(self):
        with self.assertRaises(ValueError):
            get_analyzer("azure", api_key="k", model="claude-opus-4-8")


if __name__ == "__main__":
    unittest.main()
