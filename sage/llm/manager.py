from sage.llm.base import BaseLLMProvider
from sage.llm.ollama import OllamaProvider


_provider: BaseLLMProvider | None = None


def get_provider() -> BaseLLMProvider:
    global _provider
    if _provider is None:
        _provider = OllamaProvider()
    return _provider


def set_provider(provider: BaseLLMProvider) -> None:
    global _provider
    _provider = provider
