"""
Sandboxed shell execution.

Only commands whose first token is in ALLOWED_COMMANDS are permitted.
Patterns in BLOCKED_PATTERNS are always rejected regardless of the first token.
"""
from __future__ import annotations

import shlex
import subprocess

from sage.tools.registry import REGISTRY

ALLOWED_COMMANDS: frozenset[str] = frozenset({
    "pytest", "python", "python3", "pip", "pip3",
    "git", "npm", "npx", "node",
    "cargo", "go", "make",
    "cat", "ls", "find", "grep", "echo", "wc", "head", "tail",
    "ruff", "mypy", "black", "isort",
})

BLOCKED_PATTERNS: tuple[str, ...] = (
    "rm -rf",
    "rm -r",
    "sudo",
    "curl | bash",
    "curl | sh",
    "wget | bash",
    "wget | sh",
    "> /dev/",
    "dd if=",
    "mkfs",
    "chmod 777",
    ":(){:|:&};:",
)

MAX_OUTPUT_CHARS = 4000
TIMEOUT_SECONDS = 30


@REGISTRY.tool
def run_command(command: str) -> str:
    """
    Run a shell command and return its output.
    Only safe, whitelisted commands are permitted (pytest, git, python, npm, etc.).
    """
    cmd_lower = command.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return f"Error: command blocked — contains forbidden pattern: '{pattern}'"

    try:
        tokens = shlex.split(command)
    except ValueError as e:
        return f"Error: could not parse command: {e}"

    if not tokens:
        return "Error: empty command"

    first = tokens[0].split("/")[-1]
    if first not in ALLOWED_COMMANDS:
        return (
            f"Error: command '{first}' is not in the allowed list.\n"
            f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    try:
        result = subprocess.run(
            tokens,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        output = result.stdout + result.stderr
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + f"\n… (truncated, {len(output)} chars total)"
        return output if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {TIMEOUT_SECONDS}s"
    except Exception as e:
        return f"Error: {e}"
