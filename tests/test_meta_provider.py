"""Meta Muse routing, privacy, request schema and failure behavior."""
import json
from types import SimpleNamespace

import pytest

from src.analyzer import OpenAIAnalyzer, get_analyzer
from src.cli import PrivacyGuardError, _build_analyzer
from src.config import Config


class FakeCompletions:
    def __init__(self, text):
        self.text = text
        self.body = None

    def create(self, **kwargs):
        self.body = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.text),
                                     finish_reason="stop")],
            model="muse-spark-1.3", usage=SimpleNamespace(prompt_tokens=10,
                                                        completion_tokens=20))


def test_meta_request_schema_and_result():
    text = json.dumps({"status": "PARTIAL_MATCH", "confidence": 90,
                       "issues": [], "summary": "Mismatch"})
    calls = FakeCompletions(text)
    client = SimpleNamespace(chat=SimpleNamespace(completions=calls))
    an = get_analyzer("meta", api_key="test", client=client)
    result = an.analyze_compliance("spec", "code", {})
    assert result.status == "PARTIAL_MATCH"
    assert an.get_model_info()["provider"] == "meta"
    assert calls.body["model"] == "muse-spark-1.3"
    assert calls.body["max_tokens"] == 8192
    assert calls.body["response_format"]["type"] == "json_schema"
    assert "max_completion_tokens" not in calls.body
    assert result.meta["prompt_token_count"] == 10


def test_meta_invalid_response_fails_closed():
    calls = FakeCompletions('{"status":"FULL_MATCH"}')
    client = SimpleNamespace(chat=SimpleNamespace(completions=calls))
    an = get_analyzer("meta", api_key="test", client=client)
    assert an.analyze_compliance("spec", "code", {}).status == "ERROR"


def test_meta_config_and_privacy(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test")
    monkeypatch.setenv("META_MODEL", "muse-ember-1.0")
    monkeypatch.delenv("PRSPEC_NO_CLOUD", raising=False)
    cfg = Config()
    an = _build_analyzer("meta", cfg)
    assert isinstance(an, OpenAIAnalyzer)
    assert an.model == "muse-ember-1.0"
    assert an.base_url == "https://api.meta.ai/v1"
    monkeypatch.setenv("PRSPEC_NO_CLOUD", "1")
    with pytest.raises(PrivacyGuardError):
        _build_analyzer("meta", cfg)


def test_meta_requires_key(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("PRSPEC_NO_CLOUD", raising=False)
    with pytest.raises(ValueError, match="MODEL_API_KEY"):
        _build_analyzer("meta", Config())
    with pytest.raises(ValueError, match="api_key"):
        get_analyzer("meta")
