"""Unit tests for Settings config."""
from pathlib import Path

from sage.config.settings import Settings


def test_defaults():
    s = Settings()
    assert s.ollama_host == "http://localhost:11434"
    assert s.default_model == "qwen2.5-coder:7b"


def test_index_dir_is_absolute():
    s = Settings()
    assert s.index_dir.is_absolute()


def test_memory_dir_under_project_root():
    s = Settings()
    assert s.memory_dir.is_relative_to(s.project_root)
