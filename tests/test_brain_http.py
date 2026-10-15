"""The real OpenAI SDK against a small fake server: Gemini-style limits, model switching,
thought-signature retries, and the budget record."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agent.brains import Brain, BrainUnavailable
from agent.safety import StopSwitch

SCRIPT, RECEIVED = [], []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):  # models list
        self._send(200, {"object": "list", "data": [
            {"id": "models/gemini-3.6-flash", "object": "model"},
            {"id": "models/gemini-3.6-flash-lite", "object": "model"},
            {"id": "models/gemini-3.6-flash-image", "object": "model"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        RECEIVED.append(body)
        status, payload = SCRIPT.pop(0)
        self._send(status, payload)

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def server_url():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    SCRIPT.clear()
    RECEIVED.clear()


def ok(text="ok"):
    return 200, {"id": "x", "object": "chat.completion", "created": 0, "model": "m",
                 "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}


def gemini_like(url, **extra):
    # A fake "Gemini": the URL must look like Google's for Gemini-specific handling.
    profile = {"label": "Gemini", "base_url": url, "api_key_env": "", "model": "gemini-flash-latest",
               "auto_switch_models": True, "model_filter": "flash", "vision": True, "timeout": 10, **extra}
    brain = Brain("gemini", profile, on_notice=NOTICES.append)
    brain.is_gemini = True
    return brain


NOTICES = []
USER = [{"role": "user", "content": "hi"}]


def test_daily_limit_switches_to_another_model(server_url):
    SCRIPT.extend([(429, {"error": {"message": "Quota exceeded for GenerateRequestsPerDayPerProjectPerModel"}}),
                   ok("from another model")])
    brain = gemini_like(server_url)
    assert brain.chat(USER, [], StopSwitch()).text == "from another model"
    assert [r["model"] for r in RECEIVED] == ["gemini-flash-latest", "gemini-3.6-flash"]
    assert any("switching to gemini-3.6-flash" in n for n in NOTICES)


def test_all_models_limited_means_unavailable(server_url):
    limit = (429, {"error": {"message": "Quota exceeded per day"}})
    SCRIPT.extend([limit] * 4)
    with pytest.raises(BrainUnavailable, match="limit"):
        gemini_like(server_url).chat(USER, [], StopSwitch())
    assert len(RECEIVED) == 3  # flash-latest, 3.6-flash, 3.6-flash-lite (image model skipped)


def test_per_minute_limit_waits_when_no_other_model(server_url):
    SCRIPT.extend([(429, {"error": {"message": "Rate limit. Please retry in 0.1s."}}), ok("after waiting")])
    brain = gemini_like(server_url, auto_switch_models=False)
    assert brain.chat(USER, [], StopSwitch()).text == "after waiting"


def test_signature_error_is_retried_with_placeholder(server_url):
    SCRIPT.extend([(400, {"error": {"message": "Function call is missing a thought_signature"}}), ok("fine")])
    history = USER + [{"role": "assistant", "content": None, "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "f", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "a", "content": "{}"}]
    assert gemini_like(server_url).chat(history, [], StopSwitch()).text == "fine"
    retried = RECEIVED[1]["messages"][1]["tool_calls"][0]
    assert retried["extra_content"]["google"]["thought_signature"] == "skip_thought_signature_validator"


def test_preferred_model_comes_back_after_cooldown(server_url):
    SCRIPT.extend([(429, {"error": {"message": "Rate limit. Please retry in 0.01s."}}), ok(), ok()])
    brain = gemini_like(server_url)
    brain.chat(USER, [], StopSwitch())
    brain._cooldown[brain.preferred_model] = 0  # limit has reset
    brain.chat(USER, [], StopSwitch())
    assert RECEIVED[-1]["model"] == "gemini-flash-latest"
