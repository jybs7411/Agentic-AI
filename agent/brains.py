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
from dataclasses import dataclass, field

from agent import config
from agent.safety import StopSwitch

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


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
        # Gemini: each model has its own free limit, so when one is used up we try the next one.
        self.auto_switch = bool(profile.get("auto_switch_models", False))
        self.model_filter = profile.get("model_filter", "")
        self._cooldown = {}  # model -> time when it may be used again
        self._candidates = None
        self.is_gemini = "generativelanguage.googleapis.com" in profile["base_url"]
        self.vision = bool(profile.get("vision", False))
        self.price_input = float(profile.get("price_input", 0))
        self.price_output = float(profile.get("price_output", 0))
        self.usage = usage
        self.budget_ok = budget_ok or (lambda: True)
        self.on_status = on_status or (lambda text: None)
        self.on_notice = on_notice or (lambda text: None)

        self._env_name = profile.get("api_key_env", "")
        self._base_url = profile["base_url"]
        self._timeout = float(profile.get("timeout", 120))
        self.missing_key = ""
        self._make_client()

    def _make_client(self):
        from openai import OpenAI
        key = config.get_key(self._env_name)
        self.missing_key = self._env_name if (self._env_name and not key) else ""
        self.client = OpenAI(api_key=key or "not-needed", base_url=self._base_url,
                             timeout=self._timeout, max_retries=0)

    @property
    def is_paid(self) -> bool:
        return self.price_input > 0 or self.price_output > 0

    # ------------------------------------------------------------------ main call

    def chat(self, messages: list, tools: list, stop: StopSwitch) -> Reply:
        import openai

        if self.missing_key:
            self._make_client()  # the key may have been added to .env since the agent started
        if self.missing_key:
            raise BrainUnavailable(f"{self.label}: no API key. Put {self.missing_key}=... in the .env file.")
        if self.is_paid and not self.budget_ok():
            raise BrainUnavailable(f"{self.label}: this month's cloud budget is used up "
                                   "(change cloud_monthly_budget_usd in settings).")

        # Go back to the preferred model once its limit has reset.
        if self.model != self.preferred_model and self._cooldown.get(self.preferred_model, 0) < time.time():
            self.model = self.preferred_model

        attempts = {"rate": 0, "server": 0, "signature": 0}
        while True:
            stop.check()
            send = messages if self.vision else without_images(messages)
            if attempts["signature"]:
                send = with_placeholder_signatures(send)
            try:
                kwargs = {"model": self.model, "messages": send}
                if tools:
                    kwargs["tools"] = tools
                response = self.client.chat.completions.create(**kwargs)
                return self._to_reply(response)

            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                attempts["server"] += 1
                if attempts["server"] > 2:
                    raise BrainUnavailable(f"{self.label}: can't connect. Check your internet.") from e
                self._wait(2 ** attempts["server"], stop, "Connection problem, retrying")

            except openai.RateLimitError as e:
                attempts["rate"] += 1
                delay = _retry_after(e) or _retry_in_text(str(e))
                daily = _daily_limit(e)
                self._cooldown[self.model] = time.time() + (6 * 3600 if daily else max(delay, 30))
                if self._switch_model("limit reached"):
                    continue
                if daily or (_quota_exhausted(e) and not self.is_gemini) or attempts["rate"] > 3 or delay > 90:
                    raise BrainUnavailable(f"{self.label}: usage limit reached ({_short(e)}).") from e
                self._wait(delay or 10 * attempts["rate"], stop, "Rate limit reached")

            except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
                raise BrainUnavailable(f"{self.label}: the API key was refused ({_short(e)}).") from e

            except openai.NotFoundError as e:
                self._cooldown[self.model] = time.time() + 24 * 3600
                if self._switch_model("model not available"):
                    continue
                raise BrainUnavailable(
                    f"{self.label}: model '{self.model}' not found. Check the model name in settings.json "
                    "(run check_setup.bat to see available names).") from e

            except openai.BadRequestError as e:
                text = str(e).lower()
                if self.is_gemini and "signature" in text and not attempts["signature"]:
                    attempts["signature"] = 1  # history came from another model: tell Gemini to skip the check
                    continue
                if self.vision and has_images(messages) and any(w in text for w in ("image", "vision", "multimodal")):
                    self.vision = False
                    self.on_notice(f"{self.label} can't read images; continuing without screenshots.")
                    continue
                if any(w in text for w in ("context", "too long", "n_ctx", "maximum", "exceed")):
                    raise BrainUnavailable(f"{self.label}: the conversation is too long for the model. "
                                           "Start a new conversation from the tray menu.") from e
                raise BrainError(f"{self.label} rejected the request: {_short(e)}") from e

            except openai.APIStatusError as e:  # 5xx and other server-side problems
                attempts["server"] += 1
                if attempts["server"] > 3:
                    raise BrainUnavailable(f"{self.label}: server error ({_short(e)}).") from e
                self._wait(2 ** attempts["server"], stop, "Server busy, retrying")

    # ------------------------------------------------------------------ helpers

    def _to_reply(self, response) -> Reply:
        if self.usage is not None and getattr(response, "usage", None):
            self.usage.record(self.name, response.usage.prompt_tokens or 0, response.usage.completion_tokens or 0,
                              self.price_input, self.price_output)
        if not response.choices:
            raise BrainError(f"{self.label} returned an empty answer.")
        msg = response.choices[0].message
        text = clean_text(msg.content or "")

        calls, raw_calls = [], []
        for tc in msg.tool_calls or []:
            raw = tc.model_dump(exclude_none=True)  # keeps provider extras (e.g. Gemini thought signatures)
            raw["id"] = raw.get("id") or f"call_{uuid.uuid4().hex[:12]}"
            raw_calls.append(raw)
            calls.append({"id": raw["id"], "name": tc.function.name,
                          "arguments": tc.function.arguments or "{}"})

        message = {"role": "assistant", "content": text if (text or not raw_calls) else None}
        if raw_calls:
            message["tool_calls"] = raw_calls
        return Reply(text=text, tool_calls=calls, message=message)

    def _wait(self, seconds: float, stop: StopSwitch, why: str):
        seconds = max(1, int(seconds) + 1)
        for left in range(seconds, 0, -1):
            self.on_status(f"{why} - waiting {left}s (Esc to stop)")
            stop.sleep(1)

    def list_models(self) -> list:
        return [m.id.removeprefix("models/") for m in self.client.models.list()]

    def _switch_model(self, reason: str) -> bool:
        """Try another model of the same provider (only for brains with auto_switch_models)."""
        if not self.auto_switch:
            return False
        if self._candidates is None:
            try:
                self._candidates = rank_models(self.list_models(), self.model_filter)
            except Exception:
                self._candidates = []
        now = time.time()
        for name in [self.preferred_model] + self._candidates:
            if name != self.model and self._cooldown.get(name, 0) < now:
                self.on_notice(f"{self.label}: {self.model} {reason}, switching to {name}.")
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
        return self.usage.month_cost() < float(self.settings["cloud_monthly_budget_usd"])

    def chain(self) -> list:
        """Brains to try for a command, in order: main, then backup."""
        main = self.brains.get(self.settings.get("main_brain", ""))
        if main is None:
            raise BrainError(f"Unknown main AI '{self.settings.get('main_brain')}'. Pick one in the tray menu.")
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
    """Gemini 3 wants a 'thought signature' on earlier tool calls. Calls made by another model (or an
    earlier Gemini model) don't have a valid one; Google documents this placeholder to skip the check."""
    out = []
    for m in messages:
        if m.get("tool_calls"):
            calls = []
            for call in m["tool_calls"]:
                call = {k: v for k, v in call.items() if k != "extra_content"}
                call["extra_content"] = {"google": {"thought_signature": "skip_thought_signature_validator"}}
                calls.append(call)
            m = {**m, "tool_calls": calls}
        out.append(m)
    return out


def _retry_in_text(text: str) -> float:
    match = re.search(r"retry in ([\d.]+)\s*s", text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else 0


def _daily_limit(error) -> bool:
    text = str(error).lower()
    return any(w in text for w in ("per day", "perday", "daily"))


def _retry_after(error) -> float:
    try:
        return float(error.response.headers.get("retry-after", 0))
    except Exception:
        return 0


def _quota_exhausted(error) -> bool:
    text = str(error).lower()
    return any(w in text for w in ("per day", "perday", "daily", "quota", "insufficient", "balance", "billing"))


def _short(error) -> str:
    text = getattr(error, "message", None) or str(error)
    return text[:300]
