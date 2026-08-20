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
    # Model serving region. Separate from the data region: the newest models
    # are not available in every location, and story data stays in asia-southeast1
    # regardless of where inference runs.
    vertex_location: str = Field(default="global", alias="SAMPAN_VERTEX_LOCATION")
    # The Live API is served from a different set of regions than the text
    # models, and native audio is not offered at `global`. Verified by probing:
    # global/gemini-live-2.5-flash works, us-central1/…-native-audio works,
    # and the Gemini API's model names do not exist on Vertex at all.
    live_location: str = Field(default="us-central1", alias="SAMPAN_LIVE_LOCATION")
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
        default="gemini-live-2.5-flash-native-audio", alias="SAMPAN_LIVE_MODEL"
    )

    # --- Quiet hours ------------------------------------------------------
    # Her son's pang of missing her arrives at 2pm, when she is awake — that is
    # why delivery is instant rather than scheduled. But a question left at
    # 11pm must not greet her at 11pm.
    timezone: str = Field(default="Asia/Kuala_Lumpur", alias="SAMPAN_TIMEZONE")
    quiet_from_hour: int = Field(default=22, alias="SAMPAN_QUIET_FROM")
    quiet_until_hour: int = Field(default=8, alias="SAMPAN_QUIET_UNTIL")

    # --- Generated imagery ------------------------------------------------
    # Both empty by default, and both are checked before anything is published:
    # a deploy without them simply has no card images, which is a product with
    # one fewer feature rather than a product that fails.
    memories_topic: str = Field(default="", alias="SAMPAN_MEMORIES_TOPIC")
    memories_bucket: str = Field(default="", alias="SAMPAN_MEMORIES_BUCKET")

    # --- Auth -------------------------------------------------------------
    # Shared secret guarding every non-public route. Cheap, and it keeps stray
    # web traffic from draining the hackathon credits.
    api_key: str = Field(default="", alias="SAMPAN_API_KEY")

    # --- Development ------------------------------------------------------
    # Opt-in, and deliberately off by default: a deployed revision that lost
    # its project id must fail loudly rather than quietly writing stories to a
    # dictionary and reporting success.
    allow_in_memory_store: bool = Field(
        default=False, alias="SAMPAN_ALLOW_IN_MEMORY_STORE"
    )

    @property
    def configured(self) -> bool:
        """True when the service has enough to talk to Google Cloud."""
        return bool(self.project_id)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def apply_genai_env(settings: Settings | None = None) -> None:
    """Export the variables ADK's internal genai client reads.

    ADK constructs its own `genai.Client` from the environment and never sees a
    settings object, so configuration has to be pushed to it rather than passed.
    Without this it looks for a Gemini API key and fails with a message about
    api-key docs, which points nowhere near the actual problem.

    Note the location split: models are served from `vertex_location`, while
    story data stays in `location`. ADK only cares about the former.
    """
    import os

    settings = settings or get_settings()
    if not settings.configured:
        return

    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.project_id)
    # ADK is only used for the live loop, so this is the live region. The
    # Archivist builds its own client and passes `vertex_location` explicitly.
    os.environ["GOOGLE_CLOUD_LOCATION"] = settings.live_location
