"""The agent's "brains": AI models reached through the OpenAI-compatible API.

This one format covers LM Studio (local), Z.ai GLM, Alibaba Qwen, DeepSeek and Gemini, so switching
is just a settings change. Problems are handled here:

- Local server not running / model missing / context too small -> BrainUnavailable (the router
  then hands the task to the next brain, e.g. the cloud)
- Rate limit (429)            -> wait and retry, then BrainUnavailable
- Server busy / network blip  -> retry with growing pauses
- Model can't read images     -> drop images and retry
- Monthly budget reached      -> paid brains refuse to run
"""

import json
import re
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
        from openai import OpenAI

        self.name = name
        self.label = profile.get("label", name)
        self.model = profile["model"]
        self.vision = bool(profile.get("vision", False))
        self.price_input = float(profile.get("price_input", 0))
        self.price_output = float(profile.get("price_output", 0))
        self.is_local = "localhost" in profile["base_url"] or "127.0.0.1" in profile["base_url"]
        self.usage = usage
        self.budget_ok = budget_ok or (lambda: True)
        self.on_status = on_status or (lambda text: None)
        self.on_notice = on_notice or (lambda text: None)

        env_name = profile.get("api_key_env", "")
        key = config.get_key(env_name)
        self.missing_key = env_name if (env_name and not key) else ""
        self.client = OpenAI(api_key=key or "not-needed", base_url=profile["base_url"],
                             timeout=float(profile.get("timeout", 120)), max_retries=0)

    @property
    def is_paid(self) -> bool:
        return self.price_input > 0 or self.price_output > 0

    # ------------------------------------------------------------------ main call

    def chat(self, messages: list, tools: list, stop: StopSwitch) -> Reply:
        import openai

        if self.missing_key:
            raise BrainUnavailable(f"{self.label}: no API key. Put {self.missing_key}=... in the .env file.")
        if self.is_paid and not self.budget_ok():
            raise BrainUnavailable(f"{self.label}: this month's cloud budget is used up "
                                   "(change cloud_monthly_budget_usd in settings).")

        attempts = {"rate": 0, "server": 0}
        while True:
            stop.check()
            send = messages if self.vision else without_images(messages)
            try:
                kwargs = {"model": self.model, "messages": send}
                if tools:
                    kwargs["tools"] = tools
                response = self.client.chat.completions.create(**kwargs)
                return self._to_reply(response)

            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                if self.is_local:
                    raise BrainUnavailable(
                        f"{self.label}: can't reach LM Studio. Open LM Studio, load a model and start the "
                        "server (Developer tab).") from e
                attempts["server"] += 1
                if attempts["server"] > 2:
                    raise BrainUnavailable(f"{self.label}: can't connect. Check your internet.") from e
                self._wait(2 ** attempts["server"], stop, "Connection problem, retrying")

            except openai.RateLimitError as e:
                attempts["rate"] += 1
                if attempts["rate"] > 3 or _quota_exhausted(e):
                    raise BrainUnavailable(f"{self.label}: usage limit reached ({_short(e)}).") from e
                self._wait(_retry_after(e) or 10 * attempts["rate"], stop, "Rate limit reached")

            except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
                raise BrainUnavailable(f"{self.label}: the API key was refused ({_short(e)}).") from e

            except openai.NotFoundError as e:
                raise BrainUnavailable(
                    f"{self.label}: model '{self.model}' not found. Check the model name in settings.json "
                    "(run check_setup.bat to see available names).") from e

            except openai.BadRequestError as e:
                text = str(e).lower()
                if self.vision and has_images(messages) and any(w in text for w in ("image", "vision", "multimodal")):
                    self.vision = False
                    self.on_notice(f"{self.label} can't read images; continuing without screenshots.")
                    continue
                if any(w in text for w in ("context", "too long", "n_ctx", "maximum", "exceed")):
                    hint = (" In LM Studio, reload the model with a bigger Context Length (16384 or more)."
                            if self.is_local else " Start a new conversation from the tray menu.")
                    raise BrainUnavailable(f"{self.label}: the conversation is too long for the model.{hint}") from e
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
        return [m.id for m in self.client.models.list()]


class BrainRouter:
    """Decides which brain(s) to use: local first, cloud as backup (in "auto" mode)."""

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
        """Brains to try for a command, in order."""
        mode = self.settings.get("brain_mode", "auto")
        local = self.brains.get(self.settings["local_brain"])
        cloud = self.brains.get(self.settings["cloud_brain"])
        if mode == "local":
            names = [local]
        elif mode == "cloud":
            names = [cloud]
        else:
            names = [local, cloud]
        chain = [b for b in names if b is not None]
        if not chain:
            raise BrainError("No brain is configured. Check local_brain / cloud_brain in settings.json.")
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
