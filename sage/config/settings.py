from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Global config lives at ~/.sage/.env — put your TAVILY_API_KEY here once
# and it works in every project automatically.
GLOBAL_ENV = Path.home() / ".sage" / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load global config first, then project-level .env overrides it.
        # Both files are optional — missing ones are silently skipped.
        env_file=(str(GLOBAL_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_host: str = "http://localhost:11434"
    default_model: str = "qwen2.5-coder:7b"
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    hf_token: str = Field(default="", alias="HF_TOKEN")

    project_root: Path = Field(default_factory=Path.cwd)

    index_dir: Path = Field(default=Path(".sage/index"))
    memory_dir: Path = Field(default=Path(".sage/memory"))

    @model_validator(mode="after")
    def resolve_dirs(self) -> "Settings":
        if not self.index_dir.is_absolute():
            self.index_dir = self.project_root / ".sage" / "index"
        if not self.memory_dir.is_absolute():
            self.memory_dir = self.project_root / ".sage" / "memory"
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()

    # Force export keys to environment for sub-libraries
    import os

    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token

    if settings.tavily_api_key:
        os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

    return settings
