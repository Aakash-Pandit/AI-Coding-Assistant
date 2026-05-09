# Sage — Local-First AI Coding Assistant

A terminal-based AI coding assistant that understands your codebase, answers questions, edits files, and runs autonomously — fully local using open-source LLMs.

```bash
sage "How does authentication work here?"
sage edit "Add input validation to the signup endpoint"
sage run "Find all TODOs and summarise what needs fixing"
```

---

## Requirements

- Python 3.11+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — must be running

---

## Installation (2 commands)

```bash
# 1. Install sage globally
pipx install git+https://github.com/Aakash-Pandit/sage.git

# 2. First-time setup: starts Docker, pulls model, confirms everything is ready
sage init
```

Done. No cloning, no configuration, no manual model downloads.

> `sage init` downloads `qwen2.5-coder:7b` (~4GB) on first run. Takes 5–10 min once, cached forever after.

### Optional — Enable web search

```bash
echo "TAVILY_API_KEY=tvly-your-key-here" > ~/.sage/.env
```

Get a free key at [tavily.com](https://tavily.com).

---

## Usage

Go into **any project** on your machine:

```bash
cd ~/your-project

# Index the codebase (run once per project, re-run after big changes)
sage index

# Ask questions — answers cite file:line sources from your code
sage "How does authentication work?"
sage "Where is the database configured?"
sage "What does the PaymentService class do?"

# Edit files — shows diff, asks approval before writing anything
sage edit "Add error handling to the login endpoint"
sage edit "Add type hints to all functions in utils.py"

# Git helpers
sage git diff            # AI summary of your changes
sage git commit          # AI-generated commit message

# Autonomous agent — handles multi-step tasks
sage run "Find all TODO comments and summarise them"
sage run "Run the tests and explain what's failing"
```

---

## Daily workflow

```bash
sage start               # once when you boot your machine (after first-time sage init)
cd ~/my-project
sage index               # once per project
sage "..."               # use freely
```

---

## Commands

| Command | Description |
|---|---|
| `sage init` | First-time setup: start Docker, pull model, confirm ready |
| `sage start` | Start the LLM server |
| `sage stop` | Stop the LLM server |
| `sage status` | Check if LLM server is running |
| `sage index` | Index current project into FAISS |
| `sage "question"` | Ask anything — RAG-backed if indexed |
| `sage edit "task"` | AI file editing with diff preview and approval |
| `sage run "task"` | Autonomous multi-step agent |
| `sage git diff` | Show and AI-summarise git diff |
| `sage git commit` | AI-generated commit message |
| `sage git log` | Recent commits |
| `sage model list` | See available local models |
| `sage model pull <name>` | Pull a new model |
| `sage model switch <name>` | Change default model |

---

## Architecture

```
sage "question"
      ↓
  Typer CLI
      ↓
  Agent Orchestrator (LangGraph)
      ↓
  Tool Router
    ├── File tools
    ├── Git tools
    ├── Shell tools (sandboxed)
    ├── Tavily web search
    ├── FAISS retrieval
    └── Ollama (Docker)
```

| Layer | Technology |
|---|---|
| LLM Runtime | Ollama in Docker |
| Default Model | qwen2.5-coder:7b |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Vector DB | FAISS |
| Code Parsing | Tree-sitter |
| Agent Framework | LangGraph |
| CLI | Typer + Rich |

---

## Configuration

| File | Purpose |
|---|---|
| `~/.sage/.env` | Global config — works across all projects |
| `your-project/.env` | Per-project config — overrides global |

```env
OLLAMA_HOST=http://localhost:11434
DEFAULT_MODEL=qwen2.5-coder:7b
TAVILY_API_KEY=your_key_here
```

---

## .gitignore

Add this to projects you use sage in:

```
.sage/
```

---

## Uninstallation

Remove Sage completely in 3 steps:

**1. Stop and remove Docker containers + model data**
```bash
sage stop

# Remove containers and the downloaded model (~4GB)
docker compose -f ~/.local/pipx/venvs/sage/lib/python*/site-packages/sage/docker/docker-compose.yml down --volumes

# Or simply remove the named Docker volume directly
docker volume rm sage_ollama_models
```

**2. Uninstall the CLI**
```bash
pipx uninstall sage
```

**3. Remove global config (optional)**
```bash
rm -rf ~/.sage
```

**4. Remove project indexes (optional)** — for each project you indexed:
```bash
rm -rf your-project/.sage
```

After these steps, Sage and all its data are completely removed from your machine.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/
```
