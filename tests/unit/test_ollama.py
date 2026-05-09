"""Unit tests for the Ollama LLM provider."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sage.llm.ollama import OllamaProvider


@pytest.fixture
def provider():
    return OllamaProvider(host="http://localhost:11434", model="qwen2.5-coder:7b")


@pytest.mark.asyncio
async def test_health_check_success(provider):
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await provider.health_check()
        assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(provider):
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        result = await provider.health_check()
        assert result is False


@pytest.mark.asyncio
async def test_chat_yields_content(provider):
    import json

    lines = [
        json.dumps({"message": {"content": "Hello"}, "done": False}),
        json.dumps({"message": {"content": " world"}, "done": False}),
        json.dumps({"done": True}),
    ]

    async def fake_aiter_lines():
        for line in lines:
            yield line

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = fake_aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for chunk in provider.chat([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

    assert chunks == ["Hello", " world"]
