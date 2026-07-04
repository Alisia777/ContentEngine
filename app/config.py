from functools import lru_cache
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Qharisma Video Factory"
    database_url: str = "sqlite:///./qharisma.db"
    media_root: Path = Path("media")
    mock_provider_enabled: bool = True
    llm_provider: str = "mock"
    openai_model: str = "gpt-5.5"
    video_provider: str = "mock"
    runway_model: str = "gen4.5"
    video_ratio: str = "720:1280"
    video_scene_duration: int = 5

    model_config = ConfigDict(env_file=".env", env_prefix="QVF_")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.media_root.mkdir(parents=True, exist_ok=True)
    (settings.media_root / "mock").mkdir(parents=True, exist_ok=True)
    (settings.media_root / "output").mkdir(parents=True, exist_ok=True)
    return settings
