from __future__ import annotations

import asyncio
import subprocess
import time

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from sage.cli import output as out
from sage.cli.commands import edit, git, index, model
from sage.cli.output import stream_response_async
from sage.config.settings import get_settings
from sage.docker.manager import DockerManager
from sage.llm.ollama import OllamaProvider

console = Console()

app = typer.Typer(
    name="sage",
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

    # Step 1 — Start Docker / Ollama
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:
        task = progress.add_task("Starting Ollama LLM server…")
        try:
            if docker.is_running():
                progress.update(task, description="Ollama already running — skipping start.")
            else:
                docker.start_ollama()
                # Wait until Ollama HTTP API is healthy
                deadline = time.time() + 60
                while time.time() < deadline:
                    if docker.is_running():
                        break
                    time.sleep(2)
                else:
                    out.print_error(
                        "Ollama did not become healthy within 60s. Is Docker Desktop running?"
                    )
                    raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            out.print_error(f"Failed to start Ollama: {e}\nIs Docker Desktop running?")
            raise typer.Exit(1)

    out.print_success("Ollama is running.")

    # Step 2 — Wait for model-init container to finish pulling the model
    console.print(
        "\n[bold]Pulling [cyan]qwen2.5-coder:7b[/cyan][/bold] — this takes 5–10 min on first run "
        "(cached forever after).\n"
        "Streaming model-init logs:\n"
    )
    result = subprocess.run(
        ["docker", "logs", "sage-model-init", "--follow"],
        capture_output=False,
    )
    if result.returncode not in (0, 1):
        # Container may not exist yet if Ollama was already healthy before compose ran model-init.
        # Try waiting a moment and re-checking.
        time.sleep(3)
        subprocess.run(["docker", "logs", "sage-model-init", "--follow"], capture_output=False)

    # Step 3 — Verify model is available
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:
        check_task = progress.add_task("Verifying model is available…")
        import httpx
        try:
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
            models = [m["name"] for m in resp.json().get("models", [])]
            model_ready = any("qwen2.5-coder" in m for m in models)
            progress.update(check_task, description="Done.")
        except Exception:
            model_ready = False

    if model_ready:
        out.print_success("Model [bold]qwen2.5-coder:7b[/bold] is ready.")
    else:
        out.print_warning(
            "Model not yet confirmed. If the pull is still running, wait and then run:\n"
            "  [bold]docker logs sage-model-init -f[/bold]"
        )

    console.print(
        "\n[bold green]Sage is ready![/bold green]\n\n"
        "Next steps:\n"
        "  [dim]cd[/dim] [cyan]~/your-project[/cyan]\n"
        "  [bold]sage index[/bold]       [dim]# index the codebase once[/dim]\n"
        "  [bold]sage \"...\"[/bold]      [dim]# start asking questions[/dim]\n"
    )


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
