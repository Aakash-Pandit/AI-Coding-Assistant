"""
Full indexing pipeline: scan → parse → embed → store.

Orchestrates all Phase-2 components and writes the FAISS index to disk.
"""
from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from sage.config.settings import get_settings
from sage.indexing.parser import Chunk, CodeParser
from sage.indexing.scanner import FileRecord, RepoScanner
from sage.rag.embedder import Embedder
from sage.rag.store import FAISSStore

console = Console()

# Embed in batches to keep memory reasonable
EMBED_BATCH = 128


class IndexingPipeline:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.scanner = RepoScanner()
        self.parser = CodeParser()
        self.embedder = Embedder()
        self.store = FAISSStore()

    def run(self, root: Path, show_progress: bool = True) -> dict:
        root = root.resolve()
        t0 = time.perf_counter()

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            disable=not show_progress,
        ) as progress:

            # 1. Scan
            scan_task = progress.add_task("Scanning files…", total=None)
            files: list[FileRecord] = self.scanner.scan(root)
            progress.update(scan_task, total=len(files), completed=len(files),
                            description=f"Scanned {len(files)} files")

            # 2. Parse
            parse_task = progress.add_task("Parsing chunks…", total=len(files))
            all_chunks: list[Chunk] = []
            for record in files:
                chunks = self.parser.parse(record)
                all_chunks.extend(chunks)
                progress.advance(parse_task)
            progress.update(parse_task,
                            description=f"Parsed {len(all_chunks)} chunks from {len(files)} files")

            # 3. Embed in batches
            embed_task = progress.add_task("Embedding…", total=len(all_chunks))
            import numpy as np

            all_embeddings_list = []
            for i in range(0, len(all_chunks), EMBED_BATCH):
                batch = all_chunks[i : i + EMBED_BATCH]
                texts = [c.content for c in batch]
                vecs = self.embedder.embed(texts)
                all_embeddings_list.append(vecs)
                progress.advance(embed_task, advance=len(batch))

            all_embeddings = (
                np.vstack(all_embeddings_list)
                if all_embeddings_list
                else np.empty((0, 384), dtype="float32")
            )
            progress.update(embed_task, description=f"Embedded {len(all_chunks)} chunks")

            # 4. Store
            store_task = progress.add_task("Saving FAISS index…", total=None)
            self.store.add(all_chunks, all_embeddings)
            self.store.save(self.settings.index_dir)
            progress.update(store_task, total=1, completed=1, description="Index saved")

        elapsed = time.perf_counter() - t0
        return {
            "files": len(files),
            "chunks": len(all_chunks),
            "elapsed": round(elapsed, 2),
            "index_dir": str(self.settings.index_dir),
        }
