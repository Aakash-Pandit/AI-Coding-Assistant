import asyncio

import typer
from rich.table import Table

from sage.cli.output import console, print_error, print_info, print_success
from sage.docker.manager import DockerManager
from sage.llm.ollama import OllamaProvider

app = typer.Typer(help="Manage local LLM models.")


@app.command("list")
def list_models() -> None:
    """List all locally available Ollama models."""
    docker = DockerManager()
    docker.ensure_running()

    provider = OllamaProvider()
    models = asyncio.run(provider.list_models())

    if not models:
        print_info("No models found. Pull one with: sage model pull <name>")
        return

    table = Table(title="Available Models", show_header=True, header_style="bold cyan")
    table.add_column("Model", style="green")
    for m in models:
        table.add_row(m)
    console.print(table)


@app.command("pull")
def pull_model(name: str = typer.Argument(..., help="Model name, e.g. qwen2.5-coder:7b")) -> None:
    """Pull a model from the Ollama registry."""
    docker = DockerManager()
    docker.ensure_running()

    provider = OllamaProvider()

    async def _pull() -> None:
        print_info(f"Pulling {name}…")
        async for status in provider.pull_model(name):
            console.print(f"  [dim]{status}[/dim]")
        print_success(f"Model '{name}' ready.")

    try:
        asyncio.run(_pull())
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("switch")
def switch_model(name: str = typer.Argument(..., help="Model name to set as default")) -> None:
    """Switch the default model (updates .env in the current directory)."""
    env_path = typer.get_app_dir("sage")
    # Simple approach: write/update .env in cwd
    import re
    from pathlib import Path

    env_file = Path(".env")
    if env_file.exists():
        content = env_file.read_text()
        if "DEFAULT_MODEL" in content:
            content = re.sub(r"DEFAULT_MODEL=.*", f"DEFAULT_MODEL={name}", content)
        else:
            content += f"\nDEFAULT_MODEL={name}\n"
        env_file.write_text(content)
    else:
        env_file.write_text(f"DEFAULT_MODEL={name}\n")
    print_success(f"Default model set to '{name}'. Restart sage to apply.")
