"""Runtime configuration, read from the environment.

Cloud Run injects these as env vars; locally they come from a .env file that is
never committed. See .env.example for the full set.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Google Cloud -----------------------------------------------------
    project_id: str = Field(default="", alias="GOOGLE_CLOUD_PROJECT")
    location: str = Field(default="asia-southeast1", alias="GOOGLE_CLOUD_LOCATION")
    firestore_database: str = Field(default="(default)", alias="FIRESTORE_DATABASE")

    # --- Models -----------------------------------------------------------
    # The hackathon requires Gemini 3.5 or newer. No Live dialog model meets
    # that bar, so compliance is satisfied via the Archivist and affect models.
    # See PRD.md section 9.2.
    archivist_model: str = Field(
        default="gemini-3.7-flash", alias="SAMPAN_ARCHIVIST_MODEL"
    )
    affect_model: str = Field(default="gemini-3.7-flash", alias="SAMPAN_AFFECT_MODEL")
    live_model: str = Field(
        default="gemini-3.1-flash-live-preview", alias="SAMPAN_LIVE_MODEL"
    )

    # --- Auth -------------------------------------------------------------
    # Shared secret guarding every non-public route. Cheap, and it keeps stray
    # web traffic from draining the hackathon credits.
    api_key: str = Field(default="", alias="SAMPAN_API_KEY")

    @property
    def configured(self) -> bool:
        """True when the service has enough to talk to Google Cloud."""
        return bool(self.project_id)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
