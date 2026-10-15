"""Voice in and out.

- Recorder: records your microphone while you hold the push-to-talk key, and returns a WAV file
  in memory. The WAV goes straight to Gemini, which understands Korean, English and German.
- Speaker: reads replies aloud with the voices installed in Windows, picking a Korean, German or
  English voice to match the language of the text.
"""

import io
import os
import queue
import re
import subprocess
import threading
import time
import wave

from agent.winutil import CREATE_NO_WINDOW

SAMPLE_RATE = 16000  # 16 kHz mono is plenty for speech and keeps uploads small


class Recorder:
    def __init__(self):
        self._stream = None
        self._frames = []
        self.started_at = 0.0

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self):
        import sounddevice as sd
        self._frames = []
        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                                      callback=lambda data, *_: self._frames.append(data.copy()))
        self._stream.start()
        self.started_at = time.time()

    def stop(self):
        """Stop recording. Returns WAV bytes, or None if the recording was too short."""
        import numpy as np
        if self._stream is None:
            return None
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._frames:
            return None
        audio = np.concatenate(self._frames)
        if len(audio) < SAMPLE_RATE * 0.4:  # shorter than 0.4 s: probably an accidental press
            return None
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(audio.tobytes())
        return buffer.getvalue()


# ---------------------------------------------------------------------- speaking

_SPEAK_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$culture = $env:AGENT_TTS_CULTURE
$voices = $s.GetInstalledVoices() | Where-Object { $_.Enabled }
$v = $voices | Where-Object { $_.VoiceInfo.Culture.Name -eq $culture } | Select-Object -First 1
if (-not $v) { $v = $voices | Where-Object { $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq $culture.Substring(0,2) } | Select-Object -First 1 }
if (-not $v) { exit 3 }
$s.SelectVoice($v.VoiceInfo.Name)
$s.Rate = [int]$env:AGENT_TTS_RATE
$s.Speak($env:AGENT_TTS_TEXT)
"""

_LIST_VOICES_SCRIPT = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name + " | " + $_.VoiceInfo.Culture.Name }
"""

_GERMAN_WORDS = re.compile(r"\b(und|ich|ist|nicht|das|die|der|ein|eine|habe|wurde|bitte|danke|ja|nein)\b", re.I)


def detect_language(text: str) -> str:
    """Pick a voice culture from the text: Korean if it has Hangul, German if it looks German, else English."""
    if re.search(r"[가-힣]", text):
        return "ko-KR"
    if re.search(r"[äöüß]", text, re.I) or len(_GERMAN_WORDS.findall(text)) >= 2:
        return "de-DE"
    return "en-US"


def clean_for_speech(text: str, max_chars: int = 350) -> str:
    text = re.sub(r"[*_#`>\[\]]", "", text)
    text = re.sub(r"[A-Za-z]:\\[^\s,]+", "", text)  # don't read long file paths aloud
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("다. "), cut.rfind("요. "))
    return cut[: end + 1] if end > 50 else cut


class Speaker:
    """Speaks text in a background thread. New speech interrupts old speech."""

    def __init__(self, rate: int = 0, on_notice=None):
        self.rate = rate
        self.on_notice = on_notice or (lambda text: None)
        self._queue = queue.Queue()
        self._process = None
        self._warned = set()
        threading.Thread(target=self._worker, daemon=True, name="speaker").start()

    def speak(self, text: str):
        self.stop()
        text = clean_for_speech(text)
        if text:
            self._queue.put(text)

    def stop(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        process = self._process
        if process and process.poll() is None:
            process.kill()

    def _worker(self):
        while True:
            text = self._queue.get()
            culture = detect_language(text)
            env = dict(os.environ, AGENT_TTS_TEXT=text, AGENT_TTS_CULTURE=culture, AGENT_TTS_RATE=str(self.rate))
            try:
                self._process = subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                     "-Command", _SPEAK_SCRIPT],
                    env=env, creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                code = self._process.wait()
                if code == 3 and culture not in self._warned:
                    self._warned.add(culture)
                    self.on_notice(f"No {culture} voice is installed in Windows, so replies in that language "
                                   "are not spoken. See README > 'Voices' to add one.")
            except Exception as e:
                self.on_notice(f"Could not speak: {e}")


def list_voices() -> list:
    out = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _LIST_VOICES_SCRIPT],
        capture_output=True, creationflags=CREATE_NO_WINDOW,
    ).stdout.decode("utf-8", errors="replace")
    return [line.strip() for line in out.splitlines() if line.strip()]
