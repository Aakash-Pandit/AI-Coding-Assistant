"""Tavily web search tool."""
from __future__ import annotations

from sage.tools.registry import REGISTRY


@REGISTRY.tool
def web_search(query: str) -> str:
    """
    Search the web for up-to-date information using Tavily.
    Use this for latest documentation, framework changes, package versions, or debugging help.
    """
    from sage.config.settings import get_settings

    settings = get_settings()
    if not settings.tavily_api_key:
        return (
            "Error: Tavily API key not configured. "
            "Set TAVILY_API_KEY in your .env file to enable web search."
        )

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query, max_results=5)

        results = response.get("results", [])
        if not results:
            return f"No results found for: {query}"

        lines = [f"Web search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   URL: {r.get('url', '')}")
            lines.append(f"   {r.get('content', '')[:300]}")
            lines.append("")

        return "\n".join(lines)
    except ImportError:
        return "Error: tavily-python not installed. Run: pip install tavily-python"
    except Exception as e:
        return f"Error during web search: {e}"
