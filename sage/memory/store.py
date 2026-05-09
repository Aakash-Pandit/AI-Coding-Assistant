"""
Persistent conversation memory store.

Saves/loads conversation history as JSON.
Optionally provides semantic search over past conversations via FAISS.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class MemoryStore:
    _FILE = "conversations.json"

    def __init__(self, memory_dir: Path) -> None:
        self._dir = memory_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / self._FILE
        self._entries: list[dict[str, Any]] = self._load_all()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_conversation(
        self,
        task: str,
        messages: list[dict],
        summary: str = "",
    ) -> None:
        entry = {
            "id": int(time.time() * 1000),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "task": task,
            "summary": summary or task,
            "messages": messages,
        }
        self._entries.append(entry)
        self._persist()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load_recent(self, n: int = 5) -> list[dict]:
        return self._entries[-n:]

    def search(self, query: str, n: int = 3) -> list[dict]:
        """Simple keyword search over stored task descriptions."""
        q = query.lower()
        scored = [
            (sum(1 for word in q.split() if word in e["task"].lower()), e)
            for e in self._entries
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for score, e in scored[:n] if score > 0]

    def clear(self) -> None:
        self._entries = []
        self._persist()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    def _persist(self) -> None:
        self._path.write_text(json.dumps(self._entries, indent=2))
