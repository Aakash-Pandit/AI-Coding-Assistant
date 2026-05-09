from __future__ import annotations

import asyncio

import typer

from sage.cli.output import console, print_error, print_info, print_success

app = typer.Typer(help="Git-aware operations.")


@app.command("diff")
def git_diff(
    staged: bool = typer.Option(False, "--staged", "-s", help="Show only staged changes."),
    summarise: bool = typer.Option(
        True, "--summarise/--no-summarise", help="AI summary of the diff."
    ),
) -> None:
    """Show and optionally summarise the current git diff with AI."""
    from sage.tools.git_tools import git_diff as _git_diff
    from sage.tools.git_tools import git_status

    status = git_status()
    console.print(f"\n[bold]Git Status[/bold]\n{status}\n")

    diff = _git_diff(staged=staged)
    if "No changes" in diff:
        print_info(diff)
        return

    console.print(f"[bold]Diff[/bold]\n{diff}\n")

    if summarise:
        _ai_summarise_diff(diff)


@app.command("commit")
def git_commit(
    push: bool = typer.Option(False, "--push", "-p", help="Push after committing."),
) -> None:
    """Generate an AI commit message for staged changes and commit."""
    from sage.tools.git_tools import git_diff as _git_diff

    diff = _git_diff(staged=True)
    if "No changes" in diff:
        print_info("No staged changes. Stage files with: git add <files>")
        return

    console.print("[bold]Staged diff:[/bold]")
    console.print(diff[:2000] + ("…" if len(diff) > 2000 else ""))
    console.print()

    asyncio.run(_generate_and_commit(diff, push))


@app.command("log")
def git_log(n: int = typer.Option(10, "--count", "-n", help="Number of commits to show.")) -> None:
    """Show recent git commits."""
    from sage.tools.git_tools import git_log as _git_log
    console.print(_git_log(n=n))


@app.command("status")
def git_status_cmd() -> None:
    """Show current git status."""
    from sage.tools.git_tools import git_status
    console.print(git_status())


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _ai_summarise_diff(diff: str) -> None:
    from sage.docker.manager import DockerManager
    from sage.llm.manager import get_provider

    try:
        DockerManager().ensure_running()
    except RuntimeError as e:
        print_error(str(e))
        return

    provider = get_provider()
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert code reviewer. Summarise the following git diff "
                "concisely: what changed and why it matters."
            ),
        },
        {"role": "user", "content": f"```diff\n{diff[:4000]}\n```"},
    ]

    console.print("[bold]AI Summary:[/bold]")
    from sage.cli.output import stream_response_sync
    stream_response_sync(provider.chat(messages, stream=True))


async def _generate_and_commit(diff: str, push: bool) -> None:
    import subprocess

    from sage.docker.manager import DockerManager
    from sage.llm.manager import get_provider

    try:
        DockerManager().ensure_running()
    except RuntimeError as e:
        print_error(str(e))
        return

    provider = get_provider()
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert at writing git commit messages "
                "following the Conventional Commits spec. "
                "Output ONLY the commit message — no explanation, no quotes, no markdown. "
                "Format: <type>(<scope>): <description>\n\n<optional body>"
            ),
        },
        {
            "role": "user",
            "content": f"Write a commit message for this diff:\n\n```diff\n{diff[:4000]}\n```",
        },
    ]

    console.print("[bold]Generating commit message…[/bold]")
    message = ""
    async for chunk in provider.chat(messages, stream=False):
        message += chunk

    message = message.strip()
    console.print(f"\n[green]{message}[/green]\n")

    confirmed = typer.confirm("Use this commit message?", default=True)
    if not confirmed:
        message = typer.prompt("Enter your commit message")

    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print_success("Committed successfully.")
        if push:
            push_result = subprocess.run(["git", "push"], capture_output=True, text=True)
            if push_result.returncode == 0:
                print_success("Pushed.")
            else:
                print_error(f"Push failed: {push_result.stderr}")
    else:
        print_error(f"Commit failed: {result.stderr}")
