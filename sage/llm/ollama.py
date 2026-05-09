import json
from collections.abc import AsyncIterator

import httpx

from sage.config.settings import get_settings
from sage.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.host = host or settings.ollama_host
        self.default_model = model or settings.default_model

    async def chat(
        self,
        messages: list[dict],
        stream: bool = True,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        target_model = model or self.default_model
        payload = {"model": target_model, "messages": messages, "stream": stream}

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("done"):
                        break
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.host}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.host}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]

    async def pull_model(self, model: str) -> AsyncIterator[dict]:
        """Pull a model and stream raw progress dicts from Ollama /api/pull."""
        payload = {"name": model, "stream": True}
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", f"{self.host}/api/pull", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield data
