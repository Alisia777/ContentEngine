from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Qharisma Video Factory"
    database_url: str = "sqlite:///./qharisma.db"
    media_root: Path = Path("media")
    mock_provider_enabled: bool = True
    generation_mode: Literal["mock", "real"] = "mock"
    allow_real_spend: bool = False
    max_video_seconds_per_run: int = 5
    max_scenes_per_real_run: int = 1
    max_provider_poll_seconds: int = 600
    llm_provider: str = "mock"
    openai_model: str = "gpt-5.5"
    video_provider: str = "mock"
    runway_model: str = "gen4.5"
    video_ratio: str = "720:1280"
    video_scene_duration: int = 5
    public_pilot_mode: bool = False
    auth_required: bool = False
    auth_dev_bypass_email: str = "owner@local.contentengine"
    supabase_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_URL", "QVF_SUPABASE_URL"))
    supabase_project_ref: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_PROJECT_REF", "QVF_SUPABASE_PROJECT_REF"))
    supabase_jwt_secret: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_JWT_SECRET", "QVF_SUPABASE_JWT_SECRET"))
    supabase_jwks_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_JWKS_URL", "QVF_SUPABASE_JWKS_URL"))
    supabase_issuer: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_ISSUER", "QVF_SUPABASE_ISSUER"))
    supabase_audience: str = Field(default="authenticated", validation_alias=AliasChoices("SUPABASE_AUDIENCE", "QVF_SUPABASE_AUDIENCE"))
    session_cookie_name: str = "qvf_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    public_pilot_default_org: str = "ALTEA Beauty"
    public_pilot_invite_only: bool = True
    public_pilot_real_spend_default_enabled: bool = False
    public_pilot_training_threshold: float = 0.8
    public_pilot_strict_training_gates: bool = True

    model_config = ConfigDict(env_file=".env", env_prefix="QVF_")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.media_root.mkdir(parents=True, exist_ok=True)
    (settings.media_root / "mock").mkdir(parents=True, exist_ok=True)
    (settings.media_root / "output").mkdir(parents=True, exist_ok=True)
    (settings.media_root / "generation_reports").mkdir(parents=True, exist_ok=True)
    return settings
