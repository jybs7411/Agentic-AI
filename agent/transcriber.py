"""Voice -> text with Gemini. One small request per voice command, so the free limit lasts long.

If the chosen model's free daily limit runs out, it switches to another available Flash model
(each model has its own free quota).
"""

import re

from agent.brains import BrainError

PROMPT = ("Transcribe this voice command exactly as spoken. The speaker uses Korean, English and "
          "sometimes German, possibly mixed in one sentence. Output only the transcript, nothing else. "
          "If there is no speech, output exactly: [silence]")


class Transcriber:
    def __init__(self, api_key: str, model: str, on_notice=None):
        self.api_key = api_key
        self.model = model
        self.on_notice = on_notice or (lambda text: None)
        self._client = None
        self._exhausted = set()

    @property
    def client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def transcribe(self, wav: bytes) -> str:
        from google.genai import errors, types

        if not self.api_key:
            raise BrainError("Voice needs a Gemini key: put GEMINI_API_KEY=... in the .env file. You can type instead.")
        for _ in range(4):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[types.Part.from_bytes(data=wav, mime_type="audio/wav"), PROMPT],
                )
                text = (response.text or "").strip()
                return "" if text == "[silence]" else text
            except errors.ClientError as e:
                if e.code == 429 or e.code == 404:
                    self._exhausted.add(self.model)
                    if self._switch_model():
                        continue
                    raise BrainError("Gemini's free voice limit is used up for today. Type your command instead.")
                raise BrainError(f"Voice recognition failed: {e.message}") from e
            except errors.ServerError:
                continue
            except Exception as e:  # network problems
                raise BrainError(f"Voice recognition failed (check internet): {e}") from e
        raise BrainError("Voice recognition is busy right now. Try again or type your command.")

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
        for name in candidates:
            if name not in self._exhausted:
                self.on_notice(f"Voice: switched from {self.model} to {name} (limit reached).")
                self.model = name
                return True
        return False
