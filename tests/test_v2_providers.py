"""PRSpec 2.0 provider behaviour: Gemini fail-closed, local OpenAI-compatible
server end-to-end (real HTTP, real openai SDK), and the --no-cloud guard."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import click
import pytest

from src.analyzer import GeminiAnalyzer, OpenAIAnalyzer, is_local_url

GOOD = '{"status": "PARTIAL_MATCH", "confidence": 70, "issues": [{"type": "X", "severity": "HIGH", "description": "d"}], "summary": "s"}'


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "config": config})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def gem_response(text, finish="STOP", version="gemini-3.8-flash-001"):
    return SimpleNamespace(
        text=text, model_version=version,
        usage_metadata=SimpleNamespace(prompt_token_count=1000, candidates_token_count=50,
                                       thoughts_token_count=200, total_token_count=1250),
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))])


def make_gemini(responses, **kw):
    models = FakeModels(responses)
    an = GeminiAnalyzer(api_key="k", client=SimpleNamespace(models=models), **kw)
    return an, models


def test_gemini_parses_json_and_records_meta():
    an, models = make_gemini([gem_response(GOOD)])
    res = an.analyze_compliance("spec", "code", {"file_name": "a.java"})
    assert res.status == "PARTIAL_MATCH" and len(res.issues) == 1
    assert res.meta["model_version"] == "gemini-3.8-flash-001"
    assert res.meta["total_token_count"] == 1250
    cfg = models.calls[0]["config"]
    assert cfg.response_mime_type == "application/json"
    assert cfg.temperature is None  # model default kept for Gemini 3+
    assert json.dumps(res.to_dict())  # meta is JSON-serialisable


def test_gemini_truncated_response_is_error_not_clean():
    an, _ = make_gemini([gem_response('{"status": "FULL_MATCH", "issues": []', finish="MAX_TOKENS")])
    res = an.analyze_compliance("s", "c", {})
    assert res.status == "ERROR" and "MAX_TOKENS" in res.summary


def test_gemini_empty_and_safety_blocked_are_errors():
    an, _ = make_gemini([gem_response("", finish="STOP")])
    assert an.analyze_compliance("s", "c", {}).status == "ERROR"
    an, _ = make_gemini([gem_response("", finish="SAFETY")])
    assert an.analyze_compliance("s", "c", {}).status == "ERROR"


def test_gemini_retries_transient_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    an, models = make_gemini([RuntimeError("503 UNAVAILABLE"), gem_response(GOOD)])
    assert an.analyze_compliance("s", "c", {}).status == "PARTIAL_MATCH"
    assert len(models.calls) == 2


def test_gemini_does_not_retry_auth_errors(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    an, models = make_gemini([RuntimeError("400 API key not valid"), gem_response(GOOD)])
    res = an.analyze_compliance("s", "c", {})
    assert res.status == "ERROR" and len(models.calls) == 1


class _Handler(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.seen.append({"path": self.path, "body": body})
        out = {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
               "choices": [{"index": 0, "finish_reason": "stop",
                            "message": {"role": "assistant", "content": GOOD}}],
               "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


def test_local_provider_end_to_end_over_http(local_server):
    _Handler.seen.clear()
    an = OpenAIAnalyzer(api_key="local", model="qwen3-coder:30b", base_url=local_server,
                        provider_name="local")
    res = an.analyze_compliance("spec", "code", {"file_name": "a.java", "eip_number": 1559})
    assert res.status == "PARTIAL_MATCH"
    req = _Handler.seen[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["body"]["model"] == "qwen3-coder:30b" and "max_tokens" in req["body"]
    assert res.meta["prompt_token_count"] == 10


def test_is_local_url():
    assert is_local_url("http://localhost:11434/v1")
    assert is_local_url("http://10.1.2.3:8000/v1")
    assert is_local_url("http://192.168.1.5/v1")
    assert not is_local_url("https://api.openai.com/v1")
    assert not is_local_url("https://generativelanguage.googleapis.com")


def test_no_cloud_guard(monkeypatch):
    from src.cli import PrivacyGuardError, _build_analyzer
    from src.config import Config
    monkeypatch.setenv("PRSPEC_NO_CLOUD", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    cfg = Config()
    with pytest.raises(PrivacyGuardError):
        _build_analyzer("gemini", cfg)
    monkeypatch.setenv("PRSPEC_LOCAL_BASE_URL", "https://example.com/v1")
    with pytest.raises(PrivacyGuardError):
        _build_analyzer("local", cfg)
    monkeypatch.setenv("PRSPEC_LOCAL_BASE_URL", "http://127.0.0.1:9/v1")
    an = _build_analyzer("local", cfg)
    assert an.get_model_info()["provider"] == "local"
    assert isinstance(PrivacyGuardError("x"), click.ClickException)


def test_gemini_default_model_and_env_override(monkeypatch):
    from src.config import Config
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert Config().gemini_config["model"] == "gemini-3.8-flash"
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    assert Config().gemini_config["model"] == "gemini-3.5-flash-lite"
