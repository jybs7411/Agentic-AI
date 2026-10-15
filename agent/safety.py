"""Safety layer: protected folders, the action log, and the stop switch."""

import json
import os
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


def _protected_roots(extra=()):
    env = os.environ
    roots = [
        env.get("SystemRoot", r"C:\Windows"),
        env.get("ProgramFiles", r"C:\Program Files"),
        env.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        env.get("ProgramData", r"C:\ProgramData"),
        env.get("APPDATA", ""),
        env.get("LOCALAPPDATA", ""),
        str(config.ROOT),  # the agent's own files
    ]
    roots.extend(extra)
    return [os.path.normcase(os.path.abspath(r)) for r in roots if r]


_extra_protected: list = []


def set_extra_protected(folders):
    _extra_protected.clear()
    _extra_protected.extend(folders or [])


def is_protected(path) -> bool:
    """True if `path` is a system folder, a drive root, or inside one of them."""
    if not path:
        return False
    p = os.path.normcase(os.path.abspath(os.path.expandvars(os.path.expanduser(str(path)))))
    if Path(p).parent == Path(p):  # a drive root like C:\
        return True
    for root in _protected_roots(_extra_protected):
        if p == root or p.startswith(root.rstrip("\\/") + os.sep):
            return True
    return False


class ActionLog:
    """Writes every action the agent takes to data/actions.log (one JSON line per action)."""

    def __init__(self, path: Path = None):
        self.path = path or config.ACTION_LOG_FILE
        self._lock = threading.Lock()

    def write(self, tool_name: str, args: dict, outcome: str, detail=None):
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "tool": tool_name,
            "args": args,
            "outcome": outcome,
        }
        if detail is not None:
            entry["detail"] = str(detail)[:500]
        with self._lock:
            self.path.parent.mkdir(exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def describe_call(tool_name: str, args: dict) -> str:
    """A short human-readable line like: delete_item  path=C:\\x.txt"""
    shown = []
    for key, value in args.items():
        text = str(value)
        if len(text) > 120:
            text = text[:117] + "..."
        shown.append(f"{key}={text}")
    return f"{tool_name}  " + ", ".join(shown)
