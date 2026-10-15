"""Tracks how many tokens each AI used this month and the estimated cost (data/usage.json).

If the file is damaged (for example the PC turned off while it was being written), it is kept aside
as usage.corrupt-<time>.json and paid AIs are paused until a new month starts: better than silently
forgetting what was spent and going over budget.
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from agent import config

log = logging.getLogger("agent")


class Usage:
    def __init__(self, path: Path = None):
        self.path = path or config.USAGE_FILE
        self._lock = threading.Lock()
        self.damaged = False

    @staticmethod
    def _month() -> str:
        return datetime.now().strftime("%Y-%m")

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not an object")
            return {m: v for m, v in data.items() if isinstance(v, dict) or m == "damaged_month"}
        except Exception as e:
            backup = self.path.with_name(f"usage.corrupt-{datetime.now():%Y%m%d-%H%M%S}.json")
            try:
                self.path.replace(backup)
            except OSError:
                pass
            log.error("usage.json was damaged (%s); kept as %s. Paid AIs paused this month.", e, backup.name)
            self.damaged = True
            return {"damaged_month": self._month()}

    def _write(self, data: dict):
        self.path.parent.mkdir(exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def record(self, brain: str, input_tokens: int, output_tokens: int, price_input: float, price_output: float):
        cost = (input_tokens * price_input + output_tokens * price_output) / 1_000_000
        with self._lock:
            data = self._load()
            month = data.setdefault(self._month(), {})
            entry = month.setdefault(brain, {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
            entry["requests"] = int(entry.get("requests", 0)) + 1
            entry["input_tokens"] = int(entry.get("input_tokens", 0)) + input_tokens
            entry["output_tokens"] = int(entry.get("output_tokens", 0)) + output_tokens
            entry["cost_usd"] = round(float(entry.get("cost_usd", 0)) + cost, 6)
            self._write(data)
        return cost

    def month_cost(self) -> float:
        """Estimated spending on all AIs this month, in US dollars (infinite if the record was damaged)."""
        with self._lock:
            data = self._load()
            if self.damaged and data.get("damaged_month") == self._month():
                self._write(data)  # remember the pause for the rest of the month
            if data.get("damaged_month") == self._month():
                return float("inf")
            month = data.get(self._month(), {})
        total = 0.0
        for entry in month.values():
            try:
                total += float(entry.get("cost_usd", 0))
            except (TypeError, ValueError, AttributeError):
                continue
        return total
