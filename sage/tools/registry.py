"""
Decorator-based tool registry.

Usage:
    @REGISTRY.tool
    def my_tool(arg1: str, arg2: int = 5) -> str:
        "Description shown to the LLM."
        ...

    schema = REGISTRY.get_schema()   # OpenAI-compatible tool list
    result = REGISTRY.execute("my_tool", {"arg1": "hello"})
"""
from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

_PYTHON_TO_JSON: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}
        self._specs: dict[str, ToolSpec] = {}

    def tool(self, fn: Callable) -> Callable:
        """Register a function as an agent tool."""
        name = fn.__name__
        description = (inspect.getdoc(fn) or "").strip()
        params = self._build_params(fn)

        self._tools[name] = fn
        self._specs[name] = ToolSpec(name=name, description=description, parameters=params)
        return fn

    def get_schema(self) -> list[dict]:
        """Return OpenAI-compatible tool definitions for LLM function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._specs.values()
        ]

    def execute(self, name: str, args: dict[str, Any]) -> str:
        if name not in self._tools:
            return f"Error: unknown tool '{name}'"
        try:
            result = self._tools[name](**args)
            return str(result) if result is not None else ""
        except Exception as e:
            return f"Error executing {name}: {e}"

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def _build_params(self, fn: Callable) -> dict:
        sig = inspect.signature(fn)
        hints = fn.__annotations__
        properties: dict[str, dict] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            annotation = hints.get(param_name, str)
            type_name = getattr(annotation, "__name__", str(annotation))
            json_type = _PYTHON_TO_JSON.get(type_name, "string")

            properties[param_name] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }


REGISTRY = ToolRegistry()
