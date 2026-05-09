"""Unit tests for the memory store."""
from pathlib import Path
import pytest

from sage.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    return MemoryStore(tmp_path)


def test_save_and_load_recent(store):
    store.save_conversation("fix auth bug", [], summary="Fixed JWT auth bug")
    store.save_conversation("add caching", [], summary="Added Redis caching")

    recent = store.load_recent(5)
    assert len(recent) == 2
    assert recent[-1]["task"] == "add caching"


def test_search_finds_relevant(store):
    store.save_conversation("implement jwt authentication", [])
    store.save_conversation("add redis caching", [])
    store.save_conversation("fix css layout bug", [])

    results = store.search("jwt authentication")
    assert len(results) >= 1
    assert "jwt" in results[0]["task"].lower()


def test_search_returns_empty_for_no_match(store):
    store.save_conversation("add redis caching", [])
    results = store.search("completely unrelated xyz topic")
    assert results == []


def test_persists_to_disk(tmp_path):
    store1 = MemoryStore(tmp_path)
    store1.save_conversation("task one", [{"role": "user", "content": "hello"}])

    store2 = MemoryStore(tmp_path)  # reload from same dir
    recent = store2.load_recent(5)
    assert len(recent) == 1
    assert recent[0]["task"] == "task one"


def test_clear(store):
    store.save_conversation("task", [])
    store.clear()
    assert store.load_recent(5) == []
