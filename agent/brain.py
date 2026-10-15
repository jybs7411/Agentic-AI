"""The connection to Gemini, with the free-tier problems handled:

- Rate limit hit (too many requests per minute)  -> wait the time Google asks, then retry.
- Daily limit used up for one model              -> switch to another free Flash model.
- Model name no longer exists                    -> pick an available Flash model automatically.
- Google temporarily overloaded / network issue  -> retry a few times with growing pauses.
"""

import re

import httpx
from google import genai
from google.genai import errors, types

from agent.safety import StopSwitch


class BrainError(Exception):
    """A problem explained in plain words, shown to the user."""


class Brain:
    def __init__(self, api_key: str, model: str, on_status=None, on_notice=None):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.on_status = on_status or (lambda text: None)
        self.on_notice = on_notice or (lambda text: None)
        self._exhausted_models = set()

    # ------------------------------------------------------------------ public

    def generate(self, contents, system_instruction: str, declarations, stop: StopSwitch):
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        server_retries = 0
        rate_retries = 0
        while True:
            stop.check()
            try:
                return self.client.models.generate_content(model=self.model, contents=contents, config=config)

            except errors.ClientError as e:
                text = f"{e.message} {e.details}"
                if e.code == 429:
                    if _is_daily_limit(text):
                        self._exhausted_models.add(self.model)
                        if self._switch_model(reason="daily free limit reached"):
                            continue
                        raise BrainError(
                            "The free daily Gemini limit is used up for all available models. "
                            "It resets at midnight Pacific time (about 4-5 pm in Korea)."
                        )
                    rate_retries += 1
                    if rate_retries > 4:
                        raise BrainError("Gemini keeps saying 'too many requests'. Please wait a minute and try again.")
                    delay = _retry_delay(e) or 20 * rate_retries
                    self._wait(delay, stop, "Free-tier speed limit reached")
                    continue
                if e.code == 404 or "not found" in text.lower() or "is not supported" in text.lower():
                    if self._switch_model(reason=f"model '{self.model}' is not available"):
                        continue
                if "API key not valid" in text or "API_KEY_INVALID" in text:
                    raise BrainError("Your Gemini API key is not valid. Check the key in the .env file.")
                if e.code == 403:
                    raise BrainError(f"Google refused the request (permission denied): {e.message}")
                raise BrainError(f"Gemini rejected the request: {e.message}")

            except (errors.ServerError, httpx.TransportError) as e:
                server_retries += 1
                if server_retries > 3:
                    if isinstance(e, httpx.TransportError):
                        raise BrainError("Cannot reach Google. Check your internet connection.")
                    raise BrainError("Gemini is overloaded right now. Please try again in a minute.")
                self._wait(2 ** server_retries, stop, "Gemini is busy, retrying")

    # ------------------------------------------------------------------ helpers

    def _wait(self, seconds: float, stop: StopSwitch, why: str):
        seconds = max(1, int(seconds) + 1)
        for left in range(seconds, 0, -1):
            self.on_status(f"{why} - waiting {left}s (press Esc to stop)")
            stop.sleep(1)
        self.on_status("Thinking...")

    def available_flash_models(self) -> list:
        """Flash models this API key can use for normal chat, best first."""
        names = []
        for m in self.client.models.list():
            if "generateContent" not in (m.supported_actions or []):
                continue
            name = (m.name or "").removeprefix("models/")
            if "flash" not in name:
                continue
            if any(word in name for word in ("image", "tts", "live", "audio", "embedding", "robotics", "computer-use")):
                continue
            names.append(name)

        def rank(name):
            version = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
            unstable = any(word in name for word in ("preview", "exp"))
            return (unstable, "lite" in name, -(float(version.group(1)) if version else 0))

        return sorted(set(names), key=rank)

    def _switch_model(self, reason: str) -> bool:
        try:
            candidates = self.available_flash_models()
        except Exception:
            candidates = []
        for name in candidates:
            if name != self.model and name not in self._exhausted_models:
                old = self.model
                self.model = name
                self.on_notice(f"Switched model from {old} to {name} ({reason}).")
                return True
        return False


def _retry_delay(error) -> float:
    try:
        for detail in error.details["error"]["details"]:
            if "RetryInfo" in detail.get("@type", ""):
                return float(str(detail["retryDelay"]).rstrip("s"))
    except Exception:
        pass
    return 0


def _is_daily_limit(text: str) -> bool:
    lowered = text.lower()
    return "perday" in lowered or "per day" in lowered or "daily" in lowered
