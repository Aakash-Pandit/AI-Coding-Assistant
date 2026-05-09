"""Unit tests for the agent orchestrator (mocked LLM)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sage.agent.orchestrator import AgentOrchestrator
from sage.agent.state import AgentState
from sage.tools.registry import ToolRegistry


# ---------- Tool parsing ----------

def test_parse_tool_calls_json_block():
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    text = '''
    I'll search the codebase for authentication.
    ```json
    {"tool": "search_codebase", "arguments": {"query": "authentication"}}
    ```
    '''
    calls = orch._parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "search_codebase"
    assert calls[0]["arguments"]["query"] == "authentication"


def test_parse_tool_calls_no_calls():
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    text = "Here is the answer to your question about Python decorators."
    calls = orch._parse_tool_calls(text)
    assert calls == []


def test_parse_multiple_tool_calls():
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    text = '''
    Step 1:
    ```json
    {"tool": "git_status", "arguments": {}}
    ```
    Step 2:
    ```json
    {"tool": "run_command", "arguments": {"command": "pytest"}}
    ```
    '''
    calls = orch._parse_tool_calls(text)
    assert len(calls) == 2
    assert calls[0]["name"] == "git_status"
    assert calls[1]["name"] == "run_command"


# ---------- Tool execution ----------

@pytest.mark.asyncio
async def test_execute_tools_appends_results():
    orch = AgentOrchestrator.__new__(AgentOrchestrator)

    reg = ToolRegistry()

    @reg.tool
    def fake_tool(x: str) -> str:
        "A fake tool."
        return f"result:{x}"

    with patch("sage.agent.orchestrator.REGISTRY", reg):
        state: AgentState = {
            "task": "test",
            "messages": [],
            "tool_calls": [{"name": "fake_tool", "arguments": {"x": "hello"}}],
            "tool_results": [],
            "iteration": 0,
            "done": False,
            "final_answer": "",
        }
        new_state = await orch._execute_tools(state)

    assert len(new_state["tool_results"]) == 1
    assert new_state["tool_results"][0]["result"] == "result:hello"
    assert len(new_state["messages"]) == 1
    assert "result:hello" in new_state["messages"][0]["content"]


# ---------- Registry ----------

def test_registry_schema_has_all_tools():
    from sage.tools import REGISTRY
    schema = REGISTRY.get_schema()
    names = [s["function"]["name"] for s in schema]
    assert "run_command" in names
    assert "read_file" in names
    assert "search_codebase" in names
    assert "git_status" in names
    assert "web_search" in names
