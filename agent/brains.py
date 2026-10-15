"""The agent's "brains": AI models reached through the OpenAI-compatible API.

This one format covers Gemini, Z.ai GLM, Alibaba Qwen, DeepSeek and OpenRouter, so switching
is just a settings change. Problems are handled here:

- Model missing / conversation too long / key refused -> BrainUnavailable (the router then hands
  the task to the backup AI)
- Rate limit (429)            -> wait and retry, then BrainUnavailable
- Server busy / network blip  -> retry with growing pauses
- Model can't read images     -> drop images and retry
- Monthly budget reached      -> paid brains refuse to run
"""

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _Pending
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from agent import config
from agent.safety import StopSwitch
from agent.texts import t

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
PLACEHOLDER_SIGNATURE = "skip_thought_signature_validator"  # documented by Google for foreign tool calls
_requests = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai-request")


class _EmptyReply(Exception):
    """The AI answered with nothing at all (no text, no tool call)."""


def _interruptible(call, stop: StopSwitch):
    """Run a (slow) request in the background and wait for it, but give up at once when Esc is pressed."""
    future = _requests.submit(call)
    while True:
        stop.check()
        try:
            return future.result(timeout=0.2)
        except _Pending:
            continue


class BrainError(Exception):
    """A problem explained in plain words, shown to the user."""


class BrainUnavailable(BrainError):
    """This brain can't be used right now; another brain may take over."""


@dataclass
class Reply:
    text: str
    tool_calls: list = field(default_factory=list)  # [{"id", "name", "arguments": "<json>"}]
    message: dict = field(default_factory=dict)     # the assistant message to keep in the conversation


class Brain:
    def __init__(self, name: str, profile: dict, usage=None, budget_ok=None, on_status=None, on_notice=None):
        self.name = name
        self.label = profile.get("label", name)
        self.model = profile["model"]
        self.preferred_model = profile["model"]
        # Gemini: each model has its own free limit. When one model's DAILY limit is used up, the next
        # candidate is used until the limit resets (per-minute limits are simply waited out).
        self.auto_switch = bool(profile.get("auto_switch_models", False))
        self.model_filter = profile.get("model_filter", "")
        self._configured_candidates = [m for m in profile.get("candidate_models", []) if isinstance(m, str)]
        self._cooldown = {}  # model -> time when it may be used again
        self._candidates = None
        self.reasoning_effort = profile.get("reasoning_effort") or None
        self._no_reasoning = set()  # models that rejected reasoning_effort
        self.is_gemini = "generativelanguage.googleapis.com" in profile["base_url"]
        self.vision = bool(profile.get("vision", False))
        self._image_errors = 0
        self.price_input = float(profile.get("price_input", 0) or 0)
        self.price_output = float(profile.get("price_output", 0) or 0)
        self.usage = usage
        self.budget_ok = budget_ok or (lambda: True)
        self.on_status = on_status or (lambda text: None)
        self.on_notice = on_notice or (lambda text: None)

        self._env_name = profile.get("api_key_env", "")
        self._base_url = profile["base_url"]
        self._timeout = float(profile.get("timeout", 120) or 120)
        self.missing_key = ""
        self._make_client()

    def _make_client(self):
        from openai import OpenAI
        key = config.get_key(self._env_name)
        self._key = key
        self.missing_key = self._env_name if (self._env_name and not key) else ""
        self.client = OpenAI(api_key=key or "not-needed", base_url=self._base_url,
                             timeout=self._timeout, max_retries=0)

    def env_missing(self) -> bool:
        """True if this AI still has no API key (re-checks .env, which may have changed)."""
        if self._env_name and config.get_key(self._env_name) != self._key:
            self._make_client()
        return bool(self.missing_key)

    @property
    def is_paid(self) -> bool:
        return self.price_input > 0 or self.price_output > 0

    # ------------------------------------------------------------------ main call

    def chat(self, messages: list, tools: list, stop: StopSwitch) -> Reply:
        import openai

        if self._env_name and config.get_key(self._env_name) != self._key:
            self._make_client()  # the key was added or changed (tray > Set API key) since the agent started
        if self.missing_key:
            raise BrainUnavailable(t("err_no_key", ai=self.label))
        if self.is_paid and not self.budget_ok():
            raise BrainUnavailable(t("err_budget", ai=self.label))

        now = time.time()
        if self.model != self.preferred_model and self._cooldown.get(self.preferred_model, 0) < now:
            self.model = self.preferred_model  # its limit has reset
        if self._cooldown.get(self.model, 0) > now and not self._switch_model("limit"):
            raise BrainUnavailable(t("err_limit", ai=self.label))  # don't waste a request we know will fail

        attempts = {"rate": 0, "server": 0, "signature": 0, "empty": 0, "images": False}
        while True:
            stop.check()
            send = self._prepare(messages, force_placeholder=bool(attempts["signature"]))
            if not self.vision or attempts["images"]:
                send = without_images(send)
            if attempts["empty"]:
                send = send + [{"role": "user", "content": "Continue: call a tool, or give your final answer."}]
            kwargs = {"model": self.model, "messages": send}
            if tools:
                kwargs["tools"] = tools
            if self.reasoning_effort and self.model not in self._no_reasoning:
                kwargs["reasoning_effort"] = self.reasoning_effort
            try:
                response = _interruptible(lambda: self.client.chat.completions.create(**kwargs), stop)
                return self._to_reply(response)

            except _EmptyReply:
                attempts["empty"] += 1
                if attempts["empty"] > 1:
                    raise BrainError(t("err_empty", ai=self.label))

            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                attempts["server"] += 1
                if attempts["server"] > 2:
                    raise BrainUnavailable(t("err_network", ai=self.label)) from e
                self._wait(2 ** attempts["server"], stop, t("network_reason"))

            except openai.RateLimitError as e:
                attempts["rate"] += 1
                detail = _error_text(e)
                if _is_daily_limit(detail) or (not self.is_gemini and _quota_exhausted(detail)):
                    self._cooldown[self.model] = _next_quota_reset()
                    if self._switch_model("daily limit"):
                        continue
                    raise BrainUnavailable(t("err_limit", ai=self.label)) from e
                delay = _retry_after(e) or _retry_in_text(detail) or 15
                if delay <= 60 and attempts["rate"] <= 2:  # a per-minute limit: just wait, same model
                    self._wait(delay, stop, t("limit_reason"))
                    continue
                self._cooldown[self.model] = time.time() + max(delay, 60)
                if self._switch_model("limit"):
                    continue
                raise BrainUnavailable(t("err_limit", ai=self.label)) from e

            except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
                raise BrainUnavailable(t("err_key_refused", ai=self.label)) from e

            except openai.NotFoundError as e:
                self._cooldown[self.model] = time.time() + 24 * 3600
                if self._switch_model("not available"):
                    continue
                raise BrainUnavailable(t("err_model", ai=self.label, model=self.model)) from e

            except openai.BadRequestError as e:
                detail = _error_text(e)
                lowered = detail.lower()
                if "reasoning" in lowered or "thinking" in lowered:
                    if self.model not in self._no_reasoning and "reasoning_effort" in kwargs:
                        self._no_reasoning.add(self.model)
                        continue
                if self.is_gemini and "signature" in lowered and not attempts["signature"]:
                    attempts["signature"] = 1
                    continue
                if (self.vision and not attempts["images"] and has_images(messages)
                        and any(w in lowered for w in ("image", "vision", "multimodal"))):
                    attempts["images"] = True  # try once without the picture
                    self._image_errors += 1
                    if self._image_errors >= 2:
                        self.vision = False
                    continue
                if _is_daily_limit(detail) or "resource_exhausted" in lowered or "quota" in lowered:
                    self._cooldown[self.model] = _next_quota_reset()
                    if self._switch_model("daily limit"):
                        continue
                    raise BrainUnavailable(t("err_limit", ai=self.label)) from e
                if any(w in lowered for w in ("context length", "context window", "too long", "token limit",
                                              "maximum context", "input token")):
                    raise BrainUnavailable(t("err_too_long", ai=self.label)) from e
                raise BrainError(t("err_rejected", ai=self.label, detail=detail[:200])) from e

            except openai.APIStatusError as e:  # 5xx and other server-side problems
                attempts["server"] += 1
                if attempts["server"] > 3:
                    raise BrainUnavailable(t("err_server", ai=self.label)) from e
                self._wait(2 ** attempts["server"], stop, t("server_reason"))

    # ------------------------------------------------------------------ helpers

    def _prepare(self, messages: list, force_placeholder: bool = False) -> list:
        """Make the conversation acceptable for this provider and model.

        Gemini checks a 'thought signature' on tool calls it made. Calls made by another model (the
        backup AI, or another Gemini model after a switch) can't have a valid one, so they get the
        placeholder Google documents for this case. Other providers get no Gemini extras at all."""
        out = []
        for m in messages:
            source = m.get("_model")
            m = {k: v for k, v in m.items() if not k.startswith("_")}
            if m.get("tool_calls"):
                calls = []
                for call in m["tool_calls"]:
                    call = dict(call)
                    if not self.is_gemini:
                        call.pop("extra_content", None)
                    elif force_placeholder or source != self.model:
                        call["extra_content"] = {"google": {"thought_signature": PLACEHOLDER_SIGNATURE}}
                    calls.append(call)
                m["tool_calls"] = calls
            out.append(m)
        return out

    def _to_reply(self, response) -> Reply:
        if self.usage is not None and getattr(response, "usage", None):
            self.usage.record(self.name, response.usage.prompt_tokens or 0, response.usage.completion_tokens or 0,
                              self.price_input, self.price_output)
        if not response.choices:
            raise _EmptyReply()
        choice = response.choices[0]
        msg = choice.message
        if choice.finish_reason == "content_filter" and not msg.tool_calls:
            raise BrainError(t("err_blocked", ai=self.label))
        text = clean_text(msg.content or "")

        calls, raw_calls = [], []
        for tc in msg.tool_calls or []:
            raw = tc.model_dump(exclude_none=True)  # keeps provider extras (e.g. Gemini thought signatures)
            raw["id"] = raw.get("id") or f"call_{uuid.uuid4().hex[:12]}"
            raw_calls.append(raw)
            calls.append({"id": raw["id"], "name": tc.function.name,
                          "arguments": tc.function.arguments or "{}"})
        if not text and not calls:
            raise _EmptyReply()

        message = {"role": "assistant", "content": text if (text or not raw_calls) else None, "_model": self.model}
        if raw_calls:
            message["tool_calls"] = raw_calls
        return Reply(text=text, tool_calls=calls, message=message)

    def _wait(self, seconds: float, stop: StopSwitch, why: str):
        seconds = max(1, int(seconds) + 1)
        for left in range(seconds, 0, -1):
            self.on_status(t("waiting_limit", why=why, left=left))
            stop.sleep(1)

    def list_models(self) -> list:
        return [m.id.removeprefix("models/") for m in self.client.models.list()]

    def _switch_model(self, reason: str) -> bool:
        """Try another model of the same provider (only for brains with auto_switch_models)."""
        if not self.auto_switch:
            return False
        if self._candidates is None:
            if self._configured_candidates:
                self._candidates = list(self._configured_candidates)
            else:
                try:
                    self._candidates = rank_models(self.list_models(), self.model_filter)
                except Exception:
                    self._candidates = []
        now = time.time()
        for name in [self.preferred_model] + self._candidates:
            if name != self.model and self._cooldown.get(name, 0) < now:
                self.on_notice(f"{self.label}: {self.model} ({reason}) -> {name}")
                self.model = name
                return True
        return False


class BrainRouter:
    """Decides which brains to use: your main AI, and a backup AI that takes over when the main one
    is unavailable (limits used up, server off, no key...)."""

    def __init__(self, settings: dict, usage=None, on_status=None, on_notice=None):
        self.settings = settings
        self.usage = usage
        self.brains = {
            name: Brain(name, profile, usage, budget_ok=self.budget_ok, on_status=on_status, on_notice=on_notice)
            for name, profile in settings["brains"].items()
        }

    def budget_ok(self) -> bool:
        if self.usage is None:
            return True
        try:
            budget = float(self.settings.get("cloud_monthly_budget_usd") or 0)
        except (TypeError, ValueError):
            budget = 0.0
        return self.usage.month_cost() < budget

    def chain(self) -> list:
        """Brains to try for a command, in order: main, then backup."""
        main = self.brains.get(self.settings.get("main_brain", ""))
        if main is None:
            raise BrainError(t("err_unknown_ai", name=self.settings.get("main_brain")))
        chain = [main]
        backup = self.brains.get(self.settings.get("backup_brain") or "")
        if backup is not None and backup is not main:
            chain.append(backup)
        return chain


# ---------------------------------------------------------------------- message helpers

def clean_text(text: str) -> str:
    """Remove the hidden 'thinking' some local models print, e.g. <think>...</think>."""
    text = THINK_BLOCK.sub("", text)
    if "</think>" in text:  # opening tag was in the prompt template
        text = text.split("</think>", 1)[1]
    return text.strip()


def has_images(messages: list) -> bool:
    return any(isinstance(m.get("content"), list) and any(p.get("type") == "image_url" for p in m["content"])
               for m in messages)


def without_images(messages: list) -> list:
    """Copy of the conversation with pictures replaced by a note (for brains that can't see)."""
    out = []
    for m in messages:
        if isinstance(m.get("content"), list):
            parts = [p if p.get("type") != "image_url" else {"type": "text", "text": "[screenshot omitted]"}
                     for p in m["content"]]
            m = {**m, "content": parts}
        out.append(m)
    return out


def parse_arguments(raw: str) -> dict:
    """Tool arguments arrive as JSON text; small models sometimes wrap it oddly."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError(f"Arguments are not valid JSON: {raw[:200]}")
        value = json.loads(match.group(0))
    if isinstance(value, str):  # double-encoded JSON
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Arguments must be a JSON object.")
    return value


def rank_models(names: list, must_contain: str = "") -> list:
    """Usable chat models, best first: stable before preview, newer before older, full before lite."""
    skip = ("image", "tts", "live", "audio", "embedding", "computer-use", "robotics", "native", "aqa", "learnlm")
    picked = [n for n in names if must_contain in n and not any(w in n for w in skip)]

    def key(name):
        version = re.search(r"(\d+(?:\.\d+)?)", name)
        return (any(w in name for w in ("preview", "exp")), "lite" in name,
                -(float(version.group(1)) if version else 0), name)

    return sorted(dict.fromkeys(picked), key=key)


def with_placeholder_signatures(messages: list) -> list:
    """All tool calls with the placeholder signature (used by tests and as a last resort)."""
    out = []
    for m in messages:
        if m.get("tool_calls"):
            calls = []
            for call in m["tool_calls"]:
                call = {k: v for k, v in call.items() if k != "extra_content"}
                call["extra_content"] = {"google": {"thought_signature": PLACEHOLDER_SIGNATURE}}
                calls.append(call)
            m = {**m, "tool_calls": calls}
        out.append(m)
    return out


def _error_text(error) -> str:
    """The provider's own error message (and the raw body, which holds e.g. Gemini's quotaId)."""
    body = getattr(error, "body", None)
    if isinstance(body, list) and body:
        body = body[0]
    message = ""
    if isinstance(body, dict):
        inner = body.get("error", body)
        if isinstance(inner, dict):
            message = str(inner.get("message", ""))
    return f"{message} {json.dumps(body, ensure_ascii=False, default=str) if body is not None else str(error)}".strip()


def _retry_in_text(text: str) -> float:
    match = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", text, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', text)
    return float(match.group(1)) if match else 0


def _is_daily_limit(text: str) -> bool:
    lowered = text.lower()
    return any(w in lowered for w in ("perday", "per day", "per_day", "daily", "limit: 0", "'limit': 0"))


def _next_quota_reset() -> float:
    """Gemini's daily limits reset at midnight Pacific time."""
    try:
        from zoneinfo import ZoneInfo
        pacific = datetime.now(ZoneInfo("America/Los_Angeles"))
        reset = (pacific + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
        return reset.timestamp()
    except Exception:
        return time.time() + 6 * 3600


def _retry_after(error) -> float:
    try:
        return float(error.response.headers.get("retry-after", 0))
    except Exception:
        return 0


def _quota_exhausted(text: str) -> bool:
    lowered = text.lower()
    return any(w in lowered for w in ("insufficient", "balance", "billing", "quota", "credit"))
