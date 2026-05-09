"""Memory manager — injects relevant past context into agent conversations."""
from __future__ import annotations

from sage.config.settings import get_settings
from sage.memory.store import MemoryStore


class MemoryManager:
    def __init__(self) -> None:
        settings = get_settings()
        self._store = MemoryStore(settings.memory_dir)

    def get_context_for(self, task: str, n: int = 3) -> str:
        """
        Return a formatted string of relevant past conversations to inject
        as context at the start of a new agent session.
        """
        relevant = self._store.search(task, n=n)
        if not relevant:
            return ""

        lines = ["## Relevant past conversations\n"]
        for entry in relevant:
            lines.append(f"**Task:** {entry['task']}")
            lines.append(f"**When:** {entry['timestamp']}")
            if entry.get("summary"):
                lines.append(f"**Summary:** {entry['summary']}")
            lines.append("")

        return "\n".join(lines)

    def save(self, task: str, messages: list[dict], summary: str = "") -> None:
        self._store.save_conversation(task, messages, summary)

    def recent(self, n: int = 5) -> list[dict]:
        return self._store.load_recent(n)
