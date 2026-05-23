from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    subdl_api_key: str = ""
    opensubtitles_api_key: str = ""
    opensubtitles_username: str = ""
    opensubtitles_password: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    data_dir: Path = Path("./data")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def subtitles_dir(self) -> Path:
        return self.data_dir / "subtitles"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.subtitles_dir.mkdir(parents=True, exist_ok=True)
    s.jobs_dir.mkdir(parents=True, exist_ok=True)
    return s
