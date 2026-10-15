"""Tracks how many tokens each brain used this month and the estimated cost (data/usage.json)."""

import json
import threading
from datetime import datetime
from pathlib import Path

from agent import config


class Usage:
    def __init__(self, path: Path = None):
        self.path = path or config.USAGE_FILE
        self._lock = threading.Lock()

    @staticmethod
    def _month() -> str:
        return datetime.now().strftime("%Y-%m")

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def record(self, brain: str, input_tokens: int, output_tokens: int, price_input: float, price_output: float):
        cost = (input_tokens * price_input + output_tokens * price_output) / 1_000_000
        with self._lock:
            data = self._load()
            month = data.setdefault(self._month(), {})
            entry = month.setdefault(brain, {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
            entry["requests"] += 1
            entry["input_tokens"] += input_tokens
            entry["output_tokens"] += output_tokens
            entry["cost_usd"] = round(entry["cost_usd"] + cost, 6)
            self.path.parent.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return cost

    def month_cost(self) -> float:
        """Estimated total spending on all brains this month, in US dollars."""
        with self._lock:
            month = self._load().get(self._month(), {})
        return sum(entry.get("cost_usd", 0) for entry in month.values())
