from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    task: str                       # original user task
    messages: list[dict]            # full conversation history (role/content dicts)
    tool_calls: list[dict]          # pending tool calls from last LLM response
    tool_results: list[dict]        # results of executed tool calls
    iteration: int                  # loop counter — prevents infinite loops
    done: bool                      # set True when agent signals completion
    final_answer: str               # populated when done=True
