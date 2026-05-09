import asyncio
from collections.abc import AsyncIterator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

console = Console()


def print_error(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]⚠[/bold yellow]  {msg}")


def print_diff(diff_text: str) -> None:
    console.print(
        Panel(
            Syntax(diff_text, "diff", theme="monokai", line_numbers=False),
            title="[bold]Proposed Changes[/bold]",
            border_style="cyan",
        )
    )


def stream_response_sync(iterator: AsyncIterator[str]) -> str:
    """
    Run an async streaming iterator from a synchronous context.
    Creates a new event loop — do NOT call this from inside an async function.
    """
    async def _run() -> str:
        return await _stream_to_console(iterator)

    return asyncio.run(_run())


async def stream_response_async(iterator: AsyncIterator[str]) -> str:
    """
    Consume an async streaming iterator from inside an async context.
    Use this inside async functions instead of stream_response_sync.
    """
    return await _stream_to_console(iterator)


async def _stream_to_console(iterator: AsyncIterator[str]) -> str:
    """Core streaming logic shared by sync and async entry points."""
    buffer = ""
    with Live(Text(""), console=console, refresh_per_second=20) as live:
        async for chunk in iterator:
            buffer += chunk
            live.update(Markdown(buffer))
    return buffer
