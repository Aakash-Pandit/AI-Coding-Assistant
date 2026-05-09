from __future__ import annotations

import asyncio
import time

import click
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typer.core import TyperGroup

from sage.cli import output as out
from sage.cli.commands import edit, git, index, model
from sage.cli.output import stream_response_async
from sage.config.settings import get_settings
from sage.docker.manager import DockerManager
from sage.llm.ollama import OllamaProvider

console = Console()


class _FreeformGroup(TyperGroup):
    """Route unknown 'subcommands' to the default callback as free-form query text."""

    def invoke(self, ctx: click.Context) -> object:
        # If the first protected arg isn't a known subcommand, treat the whole
        # thing as a free-form query and let the group callback handle it.
        if ctx._protected_args:
            cmd_name = ctx._protected_args[0]
            if cmd_name not in self.commands:
                ctx.args = list(ctx._protected_args) + list(ctx.args)
                ctx._protected_args = []
        return super().invoke(ctx)


app = typer.Typer(
    name="sage",
    cls=_FreeformGroup,
    help='Local-first AI coding assistant. Just ask: sage "your question"',
    no_args_is_help=False,
    rich_markup_mode="rich",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)

app.add_typer(model.app, name="model")
app.add_typer(index.app, name="index")
app.add_typer(edit.app, name="edit")
app.add_typer(git.app, name="git")


@app.command(name="init")
def init() -> None:
    """First-time setup: start Docker, pull model, and confirm everything is ready."""
    docker = DockerManager()

    # Step 1 — Start Ollama
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:
        task = progress.add_task("Starting Ollama LLM server…")
        try:
            if docker.is_running():
                progress.update(task, description="Ollama already running.")
            else:
                docker.start_ollama()
                deadline = time.time() + 60
                while time.time() < deadline:
                    if docker.is_running():
                        break
                    time.sleep(2)
                else:
                    out.print_error(
                        "Ollama did not become healthy within 60s. "
                        "Is Docker Desktop running?"
                    )
                    raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            out.print_error(f"Failed to start Ollama: {e}\nIs Docker Desktop running?")
            raise typer.Exit(1)

    out.print_success("Ollama is running.")

    # Step 2 — Pull model with live progress bar
    settings = get_settings()
    model_name = settings.default_model

    try:
        asyncio.run(_pull_model_with_progress(model_name))
    except Exception as e:
        out.print_error(f"Model pull failed: {e}")
        raise typer.Exit(1)

    console.print(
        "\n[bold green]Sage is ready![/bold green]\n\n"
        "Next steps:\n"
        "  [dim]cd[/dim] [cyan]~/your-project[/cyan]\n"
        "  [bold]sage index[/bold]       [dim]# index the codebase once[/dim]\n"
        "  [bold]sage \"...\"[/bold]      [dim]# start asking questions[/dim]\n"
    )


async def _pull_model_with_progress(model_name: str) -> None:
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    provider = OllamaProvider()

    # Check if model already exists
    try:
        existing = await provider.list_models()
        if any(model_name in m for m in existing):
            out.print_success(f"Model [bold]{model_name}[/bold] already downloaded.")
            return
    except Exception:
        pass

    console.print(
        f"\n[bold]Pulling [cyan]{model_name}[/cyan][/bold] "
        "— first run takes 5–10 min (~4 GB), cached forever after.\n"
    )

    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(f"Downloading {model_name}", total=None)
        current_digest = ""

        async for data in provider.pull_model(model_name):
            status = data.get("status", "")
            total = data.get("total")
            completed = data.get("completed")
            digest = data.get("digest", "")

            # New layer starting — reset progress for this layer
            if digest and digest != current_digest:
                current_digest = digest
                short = digest.split(":")[-1][:12] if ":" in digest else digest[:12]
                progress.update(task_id, description=f"Pulling {short}", total=total, completed=0)
            elif total and completed is not None:
                progress.update(task_id, total=total, completed=completed)
            elif status and not total:
                # Status-only lines: "pulling manifest", "verifying sha256", etc.
                progress.update(task_id, description=status, total=None, completed=0)

    out.print_success(f"Model [bold]{model_name}[/bold] is ready.")


@app.command(name="start")
def start(
    logs: bool = typer.Option(False, "--logs", "-l", help="Follow logs after starting."),
) -> None:
    """Start the Ollama LLM server (pulls model automatically on first run)."""
    docker = DockerManager()
    if docker.is_running():
        out.print_success("Sage is already running.")
        return

    out.print_info("Starting Sage LLM server…")
    try:
        docker.start_ollama()
        out.print_success("Sage started. Model will download automatically on first use.")
        out.print_info("Run [bold]docker logs sage-model-init -f[/bold] to watch model download.")
        if logs:
            import subprocess
            subprocess.run(["docker", "logs", "sage-model-init", "-f"])
    except Exception as e:
        out.print_error(f"Failed to start: {e}\nIs Docker Desktop running?")
        raise typer.Exit(1)


@app.command(name="stop")
def stop() -> None:
    """Stop the Ollama LLM server."""
    out.print_info("Stopping Sage LLM server…")
    try:
        DockerManager().stop_ollama()
        out.print_success("Sage stopped.")
    except Exception as e:
        out.print_error(str(e))
        raise typer.Exit(1)


@app.command(name="status")
def status() -> None:
    """Check if the Ollama LLM server is running."""
    if DockerManager().is_running():
        out.print_success("Sage LLM server is running.")
    else:
        out.print_warning("Sage LLM server is not running. Start it with: [bold]sage start[/bold]")


@app.command(name="run")
def run_agent(
    task: str = typer.Argument(..., help="Task for the autonomous agent to complete."),
    model_name: str | None = typer.Option(None, "--model", "-m"),
) -> None:
    """Run the autonomous agent on a multi-step task (uses all tools)."""
    _ensure_docker()
    console.print(f"\n[bold cyan]Sage Agent[/bold cyan] — [dim]{task}[/dim]\n")

    async def _run() -> None:
        from sage.agent.orchestrator import AgentOrchestrator
        from sage.memory.manager import MemoryManager

        memory = MemoryManager()
        ctx = memory.get_context_for(task)
        full_task = f"{ctx}\n\n{task}" if ctx else task

        orchestrator = AgentOrchestrator(model=model_name)
        await stream_response_async(orchestrator.run_streamed(full_task))
        memory.save(task, [], summary=task)

    try:
        asyncio.run(_run())
    except Exception as e:
        out.print_error(str(e))
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    model_name: str | None = typer.Option(
        None, "--model", "-m", help="Override the default model for this query."
    ),
    agent_mode: bool = typer.Option(
        False, "--agent", "-a", help="Use autonomous agent mode (multi-step, all tools)."
    ),
) -> None:
    """
    [bold]sage[/bold] — Local-first AI coding assistant.

    [dim]Examples:[/dim]
      sage [green]"Explain the authentication flow"[/green]
      sage [green]"Where is JWT implemented?"[/green]
      sage --agent [green]"Find all TODOs and create a summary"[/green]
      sage edit [green]"Add Redis caching to product API"[/green]
      sage index
      sage run [green]"Add auth, write tests, update README"[/green]
      sage model list
    """
    if ctx.invoked_subcommand is not None:
        return

    query = " ".join(ctx.args).strip()
    if not query:
        console.print(ctx.get_help())
        return

    if agent_mode:
        _run_with_agent(query, model_name)
    else:
        _do_ask(query, model_name)


# ------------------------------------------------------------------
# Routing logic
# ------------------------------------------------------------------

def _ensure_docker() -> None:
    docker = DockerManager()
    try:
        docker.ensure_running()
    except RuntimeError as e:
        out.print_error(str(e))
        raise typer.Exit(1)


def _do_ask(query: str, model_name: str | None) -> None:
    _ensure_docker()
    settings = get_settings()
    index_path = settings.index_dir / "repo.faiss"

    if index_path.exists():
        _ask_with_rag(query, model_name)
    else:
        out.print_warning(
            "No index found. Run [bold]sage index[/bold] for codebase-aware answers."
        )
        _ask_direct(query, model_name)


def _ask_direct(query: str, model_name: str | None) -> None:
    provider = OllamaProvider(model=model_name)
    messages = [
        {
            "role": "system",
            "content": (
                "You are Sage, an expert AI coding assistant. "
                "Answer questions clearly and concisely. "
                "When showing code, always use fenced code blocks with the language tag."
            ),
        },
        {"role": "user", "content": query},
    ]
    try:
        out.stream_response_sync(provider.chat(messages, stream=True))
    except Exception as e:
        out.print_error(f"LLM request failed: {e}")
        raise typer.Exit(1)


def _ask_with_rag(query: str, model_name: str | None) -> None:
    try:
        from sage.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline(model=model_name)
        out.stream_response_sync(pipeline.answer(query))
    except Exception as e:
        out.print_error(f"RAG pipeline failed: {e}. Falling back to direct LLM.")
        _ask_direct(query, model_name)


def _run_with_agent(task: str, model_name: str | None) -> None:
    console.print(f"\n[bold cyan]Sage Agent[/bold cyan] — [dim]{task}[/dim]\n")

    async def _run() -> None:
        from sage.agent.orchestrator import AgentOrchestrator
        from sage.memory.manager import MemoryManager

        memory = MemoryManager()
        ctx = memory.get_context_for(task)
        full_task = f"{ctx}\n\n{task}" if ctx else task

        orchestrator = AgentOrchestrator(model=model_name)
        await stream_response_async(orchestrator.run_streamed(full_task))
        memory.save(task, [], summary=task)

    try:
        asyncio.run(_run())
    except Exception as e:
        out.print_error(str(e))
        raise typer.Exit(1)
