"""Safety layer: protected folders, private files, risky words, the action log, and the stop switch."""

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from agent import config


class StopRequested(Exception):
    """Raised when you press the stop key while the agent is working."""


class StopSwitch:
    def __init__(self):
        self._event = threading.Event()

    def press(self):
        self._event.set()

    def reset(self):
        self._event.clear()

    @property
    def pressed(self) -> bool:
        return self._event.is_set()

    def check(self):
        if self._event.is_set():
            raise StopRequested()

    def sleep(self, seconds: float):
        """Wait, but wake up immediately if stop is pressed."""
        if self._event.wait(seconds):
            raise StopRequested()


# ---------------------------------------------------------------------- per-command state

# Reset at the start of every command. "private_data_read" turns on once the agent has read the
# user's files, clipboard, selection or screen text; from then on, anything that could send data
# out (opening addresses with data in them, typing long text into web pages) asks first.
session = {"private_data_read": False, "unattended": False}


def new_command(unattended: bool = False):
    session.update(private_data_read=False, unattended=unattended)


def mark_private_data_read():
    session["private_data_read"] = True


# ---------------------------------------------------------------------- paths

def _protected_roots(extra=()):
    env = os.environ
    roots = [
        env.get("SystemRoot", r"C:\Windows"),
        env.get("ProgramFiles", r"C:\Program Files"),
        env.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        env.get("ProgramData", r"C:\ProgramData"),
        env.get("APPDATA", ""),       # includes the Startup folder
        env.get("LOCALAPPDATA", ""),
        str(config.ROOT),             # the agent's own files, settings, keys and data
    ]
    roots.extend(extra)
    return [_normalize(r) for r in roots if r]


def _long_path(path: str) -> str:
    """Expand Windows 8.3 short names (C:\\PROGRA~1 -> C:\\Program Files)."""
    if os.name != "nt":
        return path
    try:
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetLongPathNameW(path, buffer, 32768):
            return buffer.value
    except Exception:
        pass
    return path


def _normalize(path) -> str:
    text = os.path.expandvars(os.path.expanduser(str(path).strip().strip('"')))
    if text.startswith("\\\\?\\") and not text.upper().startswith("\\\\?\\UNC\\"):
        text = text[4:]
    text = os.path.realpath(text)  # follows symlinks / junctions
    return os.path.normcase(_long_path(text)).rstrip(" .")


_extra_protected: list = []


def set_extra_protected(folders):
    _extra_protected.clear()
    _extra_protected.extend(folders or [])


def is_protected(path) -> bool:
    """True if `path` is a system folder, a drive root, a network path, or inside one of them."""
    if not path:
        return False
    raw = str(path).strip()
    if raw.startswith("\\\\") or raw.startswith("//"):  # network shares and \\?\UNC paths
        return True
    p = _normalize(raw)
    if Path(p).parent == Path(p):  # a drive root like C:\
        return True
    for root in _protected_roots(_extra_protected):
        if p == root or p.startswith(root.rstrip("\\/") + os.sep):
            return True
    return False


def is_private_file(path) -> bool:
    """Files the agent must never read: API keys, settings, its own data and browser profile."""
    p = _normalize(path)
    private = [config.ENV_FILE, config.SETTINGS_FILE, config.DATA_DIR]
    for item in private:
        root = _normalize(item)
        if p == root or p.startswith(root.rstrip("\\/") + os.sep):
            return True
    return Path(p).name.lower() in (".env", "id_rsa", "id_ed25519") or Path(p).suffix.lower() in (".pem", ".key", ".kdbx")


# Files that are safe to open with their default app. Anything else (programs, scripts, shortcuts,
# installers, macro documents...) asks first.
SAFE_OPEN_EXTS = {
    ".pdf", ".txt", ".md", ".csv", ".rtf", ".odt", ".ods", ".odp", ".docx", ".doc", ".xlsx", ".xls", ".pptx",
    ".ppt", ".hwp", ".hwpx", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff", ".svg",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv",
    ".zip", ".json", ".xml", ".log", ".epub",
}


# ---------------------------------------------------------------------- risky words

def risky_word_in(text: str, words) -> str:
    """The first risky word found in `text`. Latin words must match whole words ("format" does not
    match "information"); Korean words match anywhere ("삭제" in "삭제하기")."""
    lowered = (text or "").lower()
    for word in words:
        w = word.lower().strip()
        if not w:
            continue
        if re.search(r"[a-zäöüß]", w):
            if re.search(r"(?<![a-zäöüß])" + re.escape(w) + r"(?![a-zäöüß])", lowered):
                return word
        elif w in lowered:
            return word
    return ""


# ---------------------------------------------------------------------- the action log

_SECRET_PATTERNS = [re.compile(p) for p in (r"AIza[0-9A-Za-z_\-]{20,}", r"sk-[0-9A-Za-z_\-]{16,}",
                                             r"(?i)(api[_-]?key|token|password|passwort|비밀번호)\s*[=:]\s*\S+")]


def redact(text: str) -> str:
    text = str(text)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[hidden]", text)
    return text


def _redact_args(args: dict) -> dict:
    out = {}
    for key, value in args.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        if key in ("text", "content", "body", "new_text", "guide", "fact") and len(text) > 200:
            out[key] = f"[{len(text)} characters]"
        else:
            out[key] = redact(text) if isinstance(value, str) else value
    return out


class ActionLog:
    """Writes every action the agent takes to data/actions.log (one JSON line per action).
    Long typed text and anything that looks like a key or password is hidden."""

    def __init__(self, path: Path = None):
        self.path = path or config.ACTION_LOG_FILE
        self._lock = threading.Lock()

    def write(self, tool_name: str, args: dict, outcome: str, detail=None):
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "tool": tool_name,
            "args": _redact_args(args),
            "outcome": outcome,
        }
        if detail is not None:
            entry["detail"] = redact(str(detail)[:500])
        with self._lock:
            self.path.parent.mkdir(exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def describe_call(tool_name: str, args: dict, full: bool = False) -> str:
    """Arguments as readable lines. full=True (confirmations) never shortens anything."""
    lines = []
    for key, value in args.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        if not full and len(text) > 120:
            text = text[:117] + "..."
        lines.append(f"{key}: {text}")
    return "\n".join(lines) if full else f"{tool_name}  " + ", ".join(lines)
