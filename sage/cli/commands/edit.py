from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from sage.cli.output import console, print_error, print_info, print_success, print_warning, print_diff

app = typer.Typer()


@app.callback(invoke_without_command=True)
def edit(task: str = typer.Argument(..., help="Describe the change to make.")) -> None:
    """Edit files in the repository using the AI agent."""
    asyncio.run(_run_edit(task))


async def _run_edit(task: str) -> None:
    from sage.editing.diff import DiffGenerator, make_diff_text
    from sage.editing.patcher import FilePatcher
    from sage.docker.manager import DockerManager

    docker = DockerManager()
    try:
        docker.ensure_running()
    except RuntimeError as e:
        print_error(str(e))
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Sage Edit[/bold cyan] — [dim]{task}[/dim]\n")

    generator = DiffGenerator()
    patcher = FilePatcher()

    with console.status("[bold]Analysing codebase and generating changes…[/bold]"):
        try:
            diffs = await generator.generate(task)
        except Exception as e:
            print_error(f"Failed to generate changes: {e}")
            raise typer.Exit(1)

    if not diffs:
        print_warning(
            "No applicable changes were generated. "
            "Try being more specific or run [bold]sage index[/bold] first."
        )
        return

    approved = []
    for diff in diffs:
        try:
            rel = diff.file_path.relative_to(Path.cwd())
        except ValueError:
            rel = diff.file_path

        console.print(f"\n[bold]File:[/bold] {rel}")
        diff_text = make_diff_text(diff.original_content, diff.new_content, str(rel))
        print_diff(diff_text)

        choice = typer.prompt(
            "Apply this change? [y]es / [n]o / [q]uit",
            default="n",
        ).strip().lower()

        if choice in ("q", "quit"):
            print_info("Aborted.")
            return
        if choice in ("y", "yes"):
            approved.append(diff)
        else:
            print_info(f"Skipped {rel}")

    if not approved:
        print_info("No changes applied.")
        return

    failed = []
    for diff in approved:
        try:
            rel = diff.file_path.relative_to(Path.cwd())
        except ValueError:
            rel = diff.file_path
        ok, err = patcher.apply(diff)
        if ok:
            print_success(f"Patched {rel}")
        else:
            print_error(f"Failed to patch {rel}: {err}")
            failed.append(str(rel))

    if failed:
        print_warning(f"{len(failed)} file(s) failed. Rolling back all changes…")
        patcher.rollback_all()
    else:
        patcher.cleanup_backups([d.file_path for d in approved])
        print_success(f"Applied {len(approved)} change(s) successfully.")
