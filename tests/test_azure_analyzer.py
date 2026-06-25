"""Tests for the Azure AI Foundry analyzer (OpenAI-compatible deployments)."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import AzureAIAnalyzer, get_analyzer


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _fake_openai(content, raise_on_create=False):
    """Build a stand-in ``openai.OpenAI`` class that returns *content*.

    The returned class records the kwargs it was constructed with on
    ``last_init`` and the last create() call on ``last_create`` so tests can
    assert how the analyzer wired up the client.
    """

    class _FakeCompletions:
        def create(self, **kwargs):
            _FakeOpenAI.last_create = kwargs
            if raise_on_create:
                raise RuntimeError("deployment unavailable")
            return _FakeCompletion(content)

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        last_init = None
        last_create = None

        def __init__(self, **kwargs):
            _FakeOpenAI.last_init = kwargs
            self.chat = _FakeChat()

    return _FakeOpenAI


_CONTEXT = {"eip_number": 1559, "eip_title": "EIP-1559", "language": "csharp"}


class TestAzureAIAnalyzer(unittest.TestCase):
    def test_full_match_is_parsed(self):
        payload = json.dumps({
            "status": "FULL_MATCH",
            "confidence": 95,
            "issues": [],
            "summary": "Implementation matches the spec.",
        })
        with patch("openai.OpenAI", _fake_openai(payload)):
            analyzer = AzureAIAnalyzer(
                api_key="k", endpoint="https://x.services.ai.azure.com/models",
                model="claude-sonnet-4-6",
            )
            result = analyzer.analyze_compliance("spec", "code", _CONTEXT)

        self.assertEqual(result.status, "FULL_MATCH")
        self.assertEqual(result.confidence, 95)
        self.assertFalse(result.has_issues)

    def test_issues_are_parsed(self):
        payload = json.dumps({
            "status": "MISSING",
            "confidence": 70,
            "issues": [{
                "type": "MISSING_CHECK",
                "severity": "HIGH",
                "spec_reference": "base fee must be burned",
                "description": "fee not burned",
            }],
            "summary": "Found one deviation.",
        })
        with patch("openai.OpenAI", _fake_openai(payload)):
            analyzer = AzureAIAnalyzer(
                api_key="k", endpoint="https://x.services.ai.azure.com/models",
                model="claude-opus-4-8",
            )
            result = analyzer.analyze_compliance("spec", "code", _CONTEXT)

        self.assertEqual(result.status, "MISSING")
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.high_severity_issues[0]["severity"], "HIGH")

    def test_api_error_returns_error_status(self):
        with patch("openai.OpenAI", _fake_openai("", raise_on_create=True)):
            analyzer = AzureAIAnalyzer(
                api_key="k", endpoint="https://x.services.ai.azure.com/models",
                model="claude-sonnet-4-6",
            )
            result = analyzer.analyze_compliance("spec", "code", _CONTEXT)

        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.confidence, 0)
        self.assertIn("Azure AI analysis failed", result.summary)

    def test_endpoint_and_deployment_wiring(self):
        fake = _fake_openai(json.dumps({"status": "FULL_MATCH", "issues": []}))
        with patch("openai.OpenAI", fake):
            analyzer = AzureAIAnalyzer(
                api_key="secret",
                endpoint="https://x.services.ai.azure.com/models/",
                model="my-deployment",
                api_version="2024-05-01-preview",
            )
            analyzer.analyze_compliance("spec", "code", _CONTEXT)

        # Trailing slash trimmed, key forwarded as api-key header, version queried.
        self.assertEqual(fake.last_init["base_url"], "https://x.services.ai.azure.com/models")
        self.assertEqual(fake.last_init["api_key"], "secret")
        self.assertEqual(fake.last_init["default_headers"], {"api-key": "secret"})
        self.assertEqual(fake.last_init["default_query"], {"api-version": "2024-05-01-preview"})
        self.assertEqual(fake.last_create["model"], "my-deployment")

    def test_no_api_version_means_no_default_query(self):
        fake = _fake_openai(json.dumps({"status": "FULL_MATCH", "issues": []}))
        with patch("openai.OpenAI", fake):
            AzureAIAnalyzer(
                api_key="k", endpoint="https://x.services.ai.azure.com/models",
                model="d",
            )
        self.assertIsNone(fake.last_init["default_query"])

    def test_missing_endpoint_raises(self):
        with patch("openai.OpenAI", _fake_openai("{}")):
            with self.assertRaises(ValueError):
                AzureAIAnalyzer(api_key="k", endpoint="", model="d")

    def test_missing_deployment_raises(self):
        with patch("openai.OpenAI", _fake_openai("{}")):
            with self.assertRaises(ValueError):
                AzureAIAnalyzer(api_key="k", endpoint="https://x", model="")

    def test_get_model_info(self):
        with patch("openai.OpenAI", _fake_openai("{}")):
            analyzer = AzureAIAnalyzer(
                api_key="k", endpoint="https://x", model="claude-opus-4-8",
            )
        info = analyzer.get_model_info()
        self.assertEqual(info["provider"], "azure")
        self.assertEqual(info["model"], "claude-opus-4-8")


class TestFactory(unittest.TestCase):
    def test_factory_builds_azure(self):
        with patch("openai.OpenAI", _fake_openai("{}")):
            analyzer = get_analyzer(
                "azure", api_key="k",
                endpoint="https://x.services.ai.azure.com/models",
                model="claude-sonnet-4-6",
            )
        self.assertIsInstance(analyzer, AzureAIAnalyzer)

    def test_factory_azure_requires_endpoint(self):
        with self.assertRaises(ValueError):
            get_analyzer("azure", api_key="k", model="d")


if __name__ == "__main__":
    unittest.main()
