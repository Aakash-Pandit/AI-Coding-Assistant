from pathlib import Path

import typer

from sage.cli.output import console, print_error, print_success

app = typer.Typer()


@app.callback(invoke_without_command=True)
def index(
    root: Path = typer.Argument(
        default=Path("."),
        help="Root directory to index (defaults to current directory).",
    ),
) -> None:
    """Index the repository for semantic code search."""
    from sage.indexing.pipeline import IndexingPipeline

    pipeline = IndexingPipeline()
    try:
        stats = pipeline.run(root, show_progress=True)
        print_success(
            f"Indexed [bold]{stats['files']}[/bold] files → "
            f"[bold]{stats['chunks']}[/bold] chunks in {stats['elapsed']}s"
        )
        console.print(f"  [dim]Index saved to: {stats['index_dir']}[/dim]")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
