"""
LangGraph ReAct agent orchestrator.

Graph:
  START → reason → (tool_call? → execute → reason) → END

The agent loops until:
  - The LLM produces no tool calls (final answer ready), or
  - MAX_ITERATIONS is reached
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from langgraph.graph import StateGraph

from sage.agent.prompts import SYSTEM_AGENT
from sage.agent.state import AgentState
from sage.llm.manager import get_provider
from sage.tools import REGISTRY

MAX_ITERATIONS = 20
TASK_COMPLETE_MARKER = "TASK COMPLETE:"


class AgentOrchestrator:
    def __init__(self, model: str | None = None) -> None:
        self._provider = get_provider()
        self._model = model
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, task: str) -> AsyncIterator[str]:
        """Run the agent and stream output tokens as they arrive."""
        initial_state: AgentState = {
            "task": task,
            "messages": [
                {"role": "system", "content": SYSTEM_AGENT},
                {"role": "user", "content": task},
            ],
            "tool_calls": [],
            "tool_results": [],
            "iteration": 0,
            "done": False,
            "final_answer": "",
        }

        state = initial_state
        while not state["done"]:
            state = await self._reason(state)
            if state["tool_calls"]:
                state = await self._execute_tools(state)
                state["iteration"] += 1
            if state["iteration"] >= MAX_ITERATIONS:
                state["done"] = True
                state["final_answer"] = (
                    f"Reached maximum iterations ({MAX_ITERATIONS}). "
                    "The task may be incomplete."
                )

        yield state["final_answer"]

    async def run_streamed(self, task: str) -> AsyncIterator[str]:
        """
        Stream the final reasoning response token-by-token.
        Tool calls are executed silently; only the final answer streams.
        """
        state: AgentState = {
            "task": task,
            "messages": [
                {"role": "system", "content": SYSTEM_AGENT},
                {"role": "user", "content": task},
            ],
            "tool_calls": [],
            "tool_results": [],
            "iteration": 0,
            "done": False,
            "final_answer": "",
        }

        # Execute tool loop without streaming
        while not state["done"] and state["iteration"] < MAX_ITERATIONS:
            state = await self._reason(state)
            if state["tool_calls"]:
                state = await self._execute_tools(state)
                state["iteration"] += 1
            else:
                break

        # Final answer — stream it
        if state["final_answer"]:
            yield state["final_answer"]
        else:
            async for chunk in self._provider.chat(
                state["messages"], stream=True, model=self._model
            ):
                yield chunk

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    def _build_tool_prompt(self) -> str:
        """Build a human-readable tool catalogue to inject into the system prompt."""
        lines = ["\n\n## Available Tools\n"]
        lines.append(
            "Call a tool using a JSON block like:\n"
            "```json\n{\"tool\": \"<name>\", \"arguments\": {<args>}}\n```\n"
        )
        for spec in REGISTRY.get_schema():
            fn = spec["function"]
            props = fn["parameters"].get("properties", {})
            args_str = ", ".join(
                f"{k}: {v.get('type', 'string')}"
                for k, v in props.items()
            )
            lines.append(f"- **{fn['name']}**({args_str}): {fn['description']}")
        return "\n".join(lines)

    async def _reason(self, state: AgentState) -> AgentState:
        """Call the LLM with current message history, injecting tool schemas into system prompt."""
        messages = list(state["messages"])

        # Inject tool catalogue into the system message on every reasoning step
        tool_prompt = self._build_tool_prompt()
        if messages and messages[0]["role"] == "system":
            messages[0] = {
                "role": "system",
                "content": messages[0]["content"] + tool_prompt,
            }

        # Collect full response (non-streaming for tool-call parsing)
        full_response = ""
        async for chunk in self._provider.chat(
            messages,
            stream=True,
            model=self._model,
        ):
            full_response += chunk

        # Check for task completion marker
        if TASK_COMPLETE_MARKER in full_response:
            state["done"] = True
            state["final_answer"] = full_response
            state["messages"] = messages + [{"role": "assistant", "content": full_response}]
            state["tool_calls"] = []
            return state

        # Try to parse tool calls from the response
        tool_calls = self._parse_tool_calls(full_response)

        state["messages"] = messages + [{"role": "assistant", "content": full_response}]
        state["tool_calls"] = tool_calls

        if not tool_calls:
            state["done"] = True
            state["final_answer"] = full_response

        return state

    async def _execute_tools(self, state: AgentState) -> AgentState:
        """Execute all pending tool calls and append results to message history."""
        results: list[dict] = []
        result_messages: list[dict] = []

        for call in state["tool_calls"]:
            tool_name = call.get("name", "")
            tool_args = call.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {}

            output = REGISTRY.execute(tool_name, tool_args)
            results.append({"tool": tool_name, "result": output})
            result_messages.append({
                "role": "user",
                "content": f"Tool `{tool_name}` returned:\n{output}",
            })

        state["tool_results"] = results
        state["messages"] = state["messages"] + result_messages
        state["tool_calls"] = []
        return state

    def _parse_tool_calls(self, text: str) -> list[dict]:
        """
        Parse tool calls from LLM output.

        The model is instructed to use JSON blocks like:
        ```json
        {"tool": "search_codebase", "arguments": {"query": "authentication"}}
        ```
        """
        calls: list[dict] = []
        import re

        # Match ```json ... ``` blocks
        pattern = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
        for match in pattern.finditer(text):
            try:
                data = json.loads(match.group(1))
                if "tool" in data:
                    calls.append({"name": data["tool"], "arguments": data.get("arguments", {})})
            except json.JSONDecodeError:
                continue

        # Also try bare JSON objects with "tool" key
        if not calls:
            bare = re.compile(r'\{"tool"\s*:\s*"([^"]+)".*?\}', re.DOTALL)
            for match in bare.finditer(text):
                try:
                    data = json.loads(match.group(0))
                    if "tool" in data:
                        calls.append({"name": data["tool"], "arguments": data.get("arguments", {})})
                except json.JSONDecodeError:
                    continue

        return calls

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine (used for visualization/export)."""
        graph = StateGraph(AgentState)
        # Nodes are handled directly in run() for streaming support
        # The graph is kept for future LangGraph Studio integration
        return graph
