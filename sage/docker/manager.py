import subprocess
import time
from importlib import resources
from pathlib import Path

import httpx

OLLAMA_URL = "http://localhost:11434/api/tags"


def _compose_file() -> Path:
    """
    Return the path to docker-compose.yml whether sage is:
    - Run from source (development)
    - Installed via pipx / pip from GitHub
    """
    # importlib.resources works correctly in both cases
    with resources.as_file(
        resources.files("sage.docker").joinpath("docker-compose.yml")
    ) as path:
        return Path(path)


class DockerManager:
    def start_ollama(self) -> None:
        compose = _compose_file()
        subprocess.run(
            ["docker", "compose", "-f", str(compose), "up", "-d"],
            check=True,
            capture_output=True,
        )

    def stop_ollama(self) -> None:
        compose = _compose_file()
        subprocess.run(
            ["docker", "compose", "-f", str(compose), "down"],
            check=True,
            capture_output=True,
        )

    def is_running(self) -> bool:
        try:
            resp = httpx.get(OLLAMA_URL, timeout=3.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def ensure_running(self, max_wait: int = 30) -> None:
        """Start Ollama if not running and wait until healthy."""
        if self.is_running():
            return

        self.start_ollama()

        deadline = time.time() + max_wait
        while time.time() < deadline:
            if self.is_running():
                return
            time.sleep(2)

        raise RuntimeError(
            f"Ollama did not become healthy within {max_wait}s. "
            "Run: sage start --logs  to see what's wrong."
        )
