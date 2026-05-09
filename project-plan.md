# AI Coding Assistant — Project Plan

> A production-grade, local-first, agentic coding assistant CLI built with Python and open-source LLMs.

---

## Core Goal

Build a terminal-based coding assistant that can:

- Understand any codebase
- Answer questions about repositories
- Edit files intelligently
- Use tools autonomously
- Search the web
- Maintain project memory
- Run locally using open-source LLMs

**Usage examples:**

```bash
sage ask "Explain authentication flow"
sage edit "Add Redis caching to product API"
```

The agent scans the current repository, retrieves relevant code, reasons about changes, and applies safe edits.

---

## Required Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| CLI | Typer |
| LLM Runtime | Ollama (in Docker) |
| LLM Models | qwen2.5-coder:7b, deepseek-coder, codestral |
| Container | Docker / Docker Compose |
| Vector DB | FAISS |
| Embeddings | Sentence Transformers |
| Web Search | Tavily |
| Agent Workflows | LangGraph |
| Code Parsing | Tree-sitter |
| Terminal UI | Rich |
| Data Models | Pydantic v2 |
| Git | GitPython |
| Diffs | difflib + unidiff |

---

## Architecture

```
User Terminal
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
  ├── Repository indexing
  └── Docker/Ollama manager
            ↓
       Local LLM (Ollama in Docker)
```

### Architecture Separation

The system strictly separates:

1. **CLI** — user-facing commands and output formatting
2. **Agent Orchestration** — LangGraph ReAct loop (think → tool → observe → repeat)
3. **Tool Execution** — modular, isolated tool registry
4. **Retrieval System** — RAG pipeline over FAISS
5. **LLM Provider** — abstracted Ollama client
6. **Memory System** — FAISS-based persistent memory
7. **File Editing** — diff-based patching with rollback

> The local LLM runtime runs inside Docker; the CLI runs locally on the host.

---

## Project Structure

```
sage/
│
├── cli/
│   ├── __init__.py
│   ├── main.py              # Typer app entry point
│   ├── commands/
│   │   ├── ask.py
│   │   ├── edit.py
│   │   ├── index.py
│   │   ├── git.py
│   │   └── model.py
│   └── output.py            # Rich console helpers
│
├── agent/
│   ├── __init__.py
│   ├── orchestrator.py      # LangGraph agent graph
│   ├── planner.py
│   ├── state.py             # AgentState Pydantic model
│   └── prompts.py
│
├── tools/
│   ├── __init__.py
│   ├── registry.py          # Tool registry (decorator-based)
│   ├── file_tools.py
│   ├── git_tools.py
│   ├── shell_tools.py       # Sandboxed execution
│   ├── search_tools.py      # Tavily integration
│   └── retrieval_tools.py
│
├── rag/
│   ├── __init__.py
│   ├── pipeline.py
│   ├── chunker.py
│   ├── embedder.py
│   ├── store.py             # FAISS wrapper
│   └── retriever.py
│
├── memory/
│   ├── __init__.py
│   ├── store.py
│   └── manager.py
│
├── llm/
│   ├── __init__.py
│   ├── base.py              # Abstract LLM provider
│   ├── ollama.py            # Ollama HTTP client
│   └── manager.py
│
├── indexing/
│   ├── __init__.py
│   ├── scanner.py           # Repo file walker
│   ├── parser.py            # Tree-sitter AST parsing
│   └── pipeline.py
│
├── editing/
│   ├── __init__.py
│   ├── diff.py
│   ├── patcher.py
│   └── validator.py
│
├── docker/
│   ├── docker-compose.yml
│   ├── manager.py           # Docker SDK integration
│   └── Dockerfile.ollama
│
├── config/
│   ├── __init__.py
│   ├── settings.py          # Pydantic Settings (env + file)
│   └── defaults.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── workspace/               # Agent scratch space
├── pyproject.toml
└── .env.example
```

---

## Feature Requirements

### 1. Repository Understanding

**Commands:**
```bash
sage index
sage ask "Where is JWT implemented?"
```

**Features:**
- Scan repository recursively
- Chunk files by semantic boundaries (function/class via Tree-sitter)
- Generate embeddings via Sentence Transformers
- Store vectors in FAISS (with JSON metadata sidecar)
- Semantic code retrieval at query time

**Supported file types:** `.py` `.go` `.js` `.ts` `.json` `.yaml` `.md`

**Ignored paths:** `venv/` `node_modules/` `.git/` `dist/` `build/`

---

### 2. Intelligent Retrieval (RAG)

- Semantic similarity search over FAISS index
- Chunk re-ranking by relevance score
- Context compression (trim low-relevance chunks before sending to LLM)
- Full retrieval pipeline with metadata tracking (file path, line numbers, language)

---

### 3. Agentic File Editing

**Command:**
```bash
sage edit "Add JWT authentication"
```

**Requirements:**
- Identify relevant files via RAG retrieval
- Generate minimal unified diffs (never rewrite entire files)
- Validate syntax before writing (AST parse check)
- Require user approval before applying changes
- Support rollback via backup snapshots

**Implementation:**
- Diff-based patching (`difflib` + `unidiff`)
- Safe atomic file writes
- Pre-edit backup, post-edit restore on failure

---

### 4. Tool Calling System

The agent autonomously decides when to use:

- Read files
- Search codebase (FAISS retrieval)
- Execute shell commands (sandboxed)
- Search the web (Tavily)
- Run tests
- Inspect git diff

Tools are registered via a decorator-based registry with auto-generated JSON schemas for LLM function calling.

---

### 5. Tavily Web Search Integration

Used for:
- Latest library documentation
- Framework API changes
- Package version references
- Debugging unknown errors

**Example:**
```bash
sage ask "latest Django async ORM improvements"
```

---

### 6. Git Integration

- Git diff awareness (staged vs. unstaged)
- Commit message generation
- PR summary generation
- Branch-aware context

---

### 7. Dockerized Model Runtime

Docker Compose manages the Ollama container.

**Requirements:**
- Lazy-start: spin up container only when needed
- Lazy-load models: pull on first use
- Persistent volume for model weights
- Easy model switching via config
- Health check before sending requests

**Supported models:**
- `qwen2.5-coder:7b`
- `deepseek-coder`
- `codestral`

---

### 8. Memory System

Stores across sessions:
- Repository summaries
- Previous conversation history
- Architecture notes
- Frequently accessed file metadata

Initial implementation uses FAISS-backed memory with JSON metadata.

---

### 9. Terminal UX (Rich)

- Colored syntax-highlighted output
- Progress bars during indexing
- Streaming LLM responses
- Unified diff visualization
- Timestamped command logs

---

### 10. Autonomous Agent Workflow (LangGraph)

Iterative ReAct loop:

```
Think → Decide Tool → Execute Tool → Observe Result → (repeat until done)
```

Supports:
- Multi-step planning
- Reflection / self-correction
- Automatic retries on tool failure
- Output validation before presenting to user

---

## Engineering Constraints

- Clean, modular architecture — no monoliths
- Strong typing with Pydantic v2 throughout
- Async-first where I/O-bound (LLM calls, file ops, HTTP)
- Every tool is isolated and independently testable
- Designed for future MCP (Model Context Protocol) support
- Extensible LLM provider abstraction (add OpenAI/Anthropic later)

---

## Security Requirements

- Shell commands run in a sandboxed subprocess with allowlist
- File writes restricted to project directory
- Mandatory user approval before any destructive action
- No arbitrary `rm`, `sudo`, or network-mutating commands without confirmation

---

## Development Phases

### Phase 1 — Foundation
- Project scaffold (`pyproject.toml`, folder structure)
- Typer CLI with `ask` command
- Ollama HTTP client + Docker Compose setup
- Basic Q&A with local LLM (no retrieval)
- Rich output with streaming

### Phase 2 — Repository Indexing
- File scanner (respects ignore patterns)
- Tree-sitter parser (chunk by function/class boundaries)
- Sentence Transformer embeddings
- FAISS index store with JSON metadata sidecar
- `sage index` command with progress bar

### Phase 3 — RAG Pipeline
- Retrieval pipeline over FAISS index
- Context compression and chunk re-ranking
- Context-aware `ask` command (retrieval + LLM)
- Metadata-rich responses (shows source files/lines)

### Phase 4 — File Editing
- Diff generation from LLM output
- Unified patch application with syntax validation
- User approval flow (Rich diff preview → confirm/reject)
- Rollback on failure
- `sage edit` command

### Phase 5 — Tool Calling
- Decorator-based tool registry
- LangGraph tool-call nodes
- Sandboxed shell execution
- Tavily web search integration
- Git diff tools

### Phase 6 — Autonomous Workflows
- Full LangGraph ReAct agent
- Multi-step planning node
- Reflection / retry logic
- Complex task execution (e.g., "add auth + tests + update README")

---

## Testing Strategy

| Phase | Test Type | Focus |
|---|---|---|
| 1 | Unit | LLM client, CLI command parsing |
| 2 | Unit + Integration | Scanner, chunker, FAISS store |
| 3 | Integration | RAG retrieval accuracy |
| 4 | Integration | Diff correctness, patch safety |
| 5 | Unit + E2E | Tool registry, sandboxed shell |
| 6 | E2E | Full agent task completion |

---

## Key Dependencies (with versions)

```toml
[project]
dependencies = [
  "typer>=0.12",
  "rich>=13.0",
  "pydantic>=2.0",
  "pydantic-settings>=2.0",
  "httpx>=0.27",           # Async Ollama client
  "faiss-cpu>=1.8",
  "sentence-transformers>=3.0",
  "langgraph>=0.2",
  "langchain-core>=0.2",
  "tree-sitter>=0.23",
  "gitpython>=3.1",
  "unidiff>=0.7",
  "tavily-python>=0.3",
  "docker>=7.0",
]
```

---

## What to Expect

- Complete architecture guidance per module
- Production-grade code with type hints throughout
- Folder-by-folder, phase-by-phase implementation
- Docker Compose setup for Ollama
- Scalable design (add models, tools, or providers later)
- Testing at every phase
- No shallow explanations — implementation details included
