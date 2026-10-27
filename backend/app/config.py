from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    foundry_project_endpoint: str = ""
    foundry_model: str = ""
    foundry_agent_name: str = "klinik-studio-discharge"
    foundry_agent_version: str = ""
    azure_tenant_id: str | None = None
    content_understanding_endpoint: str = ""
    content_understanding_analyzer: str = ""
    database_path: Path = ROOT / ".local" / "cockpit.sqlite3"


settings = Settings()
