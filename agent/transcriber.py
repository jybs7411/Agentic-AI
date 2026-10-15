"""Voice -> text with Gemini. One small request per voice command.

The default voice model is a "lite" Flash model: it has its own free limit, so voice commands don't
use up the main AI's requests. If a model's limit is reached, another Flash model is used for a
while (per-minute limits: 1 minute; daily limits: until midnight Pacific time).
"""

import re
import time

from agent.brains import BrainError, _next_quota_reset
from agent.texts import t

PROMPT = ("Transcribe this voice command exactly as spoken. The speaker uses Korean, English and "
          "sometimes German, possibly mixed in one sentence. Do not translate. Write Korean in Hangul and "
          "keep English and German words as spoken. Output only the transcript, nothing else. "
          "If there is no speech, output exactly: [silence]")


class Transcriber:
    def __init__(self, api_key: str, model: str, on_notice=None, extra_names=None):
        self.api_key = api_key
        self.model = model
        self.preferred_model = model
        self.on_notice = on_notice or (lambda text: None)
        self.extra_names = extra_names or (lambda: [])  # e.g. routine names, so they're spelled right
        self._client = None
        self._cooldown = {}
        self._no_thinking_config = set()

    @property
    def client(self):
        if self._client is None:
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=30000))
        return self._client

    def _prompt(self) -> str:
        names = [n for n in self.extra_names() if n][:30]
        return PROMPT + (f" Names that may be said: {', '.join(names)}." if names else "")

    def transcribe(self, wav: bytes) -> str:
        from google.genai import errors, types

        if not self.api_key:
            raise BrainError(t("voice_no_key"))
        if self.model != self.preferred_model and self._cooldown.get(self.preferred_model, 0) < time.time():
            self.model = self.preferred_model
        for _ in range(4):
            config = None
            if self.model not in self._no_thinking_config:  # transcription needs no "thinking": faster
                config = types.GenerateContentConfig(temperature=0, thinking_config=types.ThinkingConfig(thinking_budget=0))
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[types.Part.from_bytes(data=wav, mime_type="audio/wav"), self._prompt()],
                    config=config,
                )
                text = (response.text or "").strip()
                return "" if text == "[silence]" else text
            except errors.ClientError as e:
                detail = f"{e.message} {e.details}".lower()
                if e.code == 400 and config is not None and "think" in detail:
                    self._no_thinking_config.add(self.model)
                    continue
                if e.code in (404, 429):
                    daily = any(w in detail for w in ("perday", "per day", "daily", "limit: 0")) or e.code == 404
                    self._cooldown[self.model] = _next_quota_reset() if daily else time.time() + 60
                    if self._switch_model():
                        continue
                    raise BrainError(t("voice_limit"))
                raise BrainError(t("voice_failed", detail=e.message)) from e
            except errors.ServerError:
                time.sleep(1.5)
                continue
            except Exception as e:  # network problems, timeouts
                raise BrainError(t("voice_failed", detail=str(e)[:150])) from e
        raise BrainError(t("voice_failed", detail="busy"))

    def available_flash_models(self) -> list:
        names = []
        for m in self.client.models.list():
            if "generateContent" not in (m.supported_actions or []):
                continue
            name = (m.name or "").removeprefix("models/")
            if "flash" in name and not any(w in name for w in ("image", "tts", "live", "embedding", "computer-use")):
                names.append(name)

        def rank(name):  # stable before preview; lite models have bigger free quotas, so prefer them for voice
            version = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
            return (any(w in name for w in ("preview", "exp")), "lite" not in name,
                    -(float(version.group(1)) if version else 0))

        return sorted(set(names), key=rank)

    def _switch_model(self) -> bool:
        try:
            candidates = self.available_flash_models()
        except Exception:
            return False
        now = time.time()
        for name in [self.preferred_model] + candidates:
            if name != self.model and self._cooldown.get(name, 0) < now:
                self.on_notice(f"Voice: {self.model} -> {name}")
                self.model = name
                return True
        return False
