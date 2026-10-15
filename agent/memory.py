"""Long-term memory: facts you ask the agent to remember, stored in data/memory.json.

You can open that file in Notepad and edit it yourself at any time.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from agent import config


class Memory:
    def __init__(self, path: Path = None):
        self.path = path or config.MEMORY_FILE
        self._lock = threading.Lock()

    def _load(self) -> list:
        """Read the file, accepting hand-edited shapes: plain strings, missing numbers, a wrapper object."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except Exception:
            return []
        if isinstance(data, dict):
            data = data.get("facts", [])
        facts, used = [], set()
        for item in data if isinstance(data, list) else []:
            if isinstance(item, str):
                item = {"fact": item}
            if not isinstance(item, dict) or not str(item.get("fact", "")).strip():
                continue
            fact_id = item.get("id")
            if not isinstance(fact_id, int) or fact_id in used:
                fact_id = max(used | {0}) + 1
            used.add(fact_id)
            facts.append({"id": fact_id, "fact": str(item["fact"]).strip(), "saved": str(item.get("saved", ""))})
        return facts

    def _save(self, facts: list):
        self.path.parent.mkdir(exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def all(self) -> list:
        with self._lock:
            return self._load()

    def add(self, fact: str) -> dict:
        with self._lock:
            facts = self._load()
            new_id = max((f["id"] for f in facts), default=0) + 1
            entry = {"id": new_id, "fact": fact.strip(), "saved": datetime.now().strftime("%Y-%m-%d")}
            facts.append(entry)
            self._save(facts)
            return entry

    def remove(self, fact_id: int) -> bool:
        with self._lock:
            facts = self._load()
            kept = [f for f in facts if f["id"] != fact_id]
            self._save(kept)
            return len(kept) != len(facts)

    def as_prompt_text(self) -> str:
        facts = self.all()
        if not facts:
            return "(nothing saved yet)"
        return "\n".join(f"- [{f['id']}] {f['fact'][:300]}" for f in facts)


_instance = None


def get_memory() -> Memory:
    global _instance
    if _instance is None:
        _instance = Memory()
    return _instance
