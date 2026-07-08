from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_base_url: str = "http://localhost:8080"
    session_secret: str = "change-me-local-secret"
    session_cookie_name: str = "rda_session"

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None

    gcp_project_id: str | None = None
    gcp_location: str = "europe-west4"
    rag_corpus_prefix: str = "proposal-review"
    gemini_model: str = "gemini-3.5-flash"
    embedding_model: str = "publishers/google/models/text-embedding-005"

    analyzer_backend: Literal["local", "gemini_rag"] = "local"
    max_document_chars: int = Field(default=100_000, ge=1_000)
    rag_chunk_size: int = Field(default=512, ge=128)
    rag_chunk_overlap: int = Field(default=100, ge=0)
    rag_top_k: int = Field(default=4, ge=1, le=20)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def oauth_redirect_uri(self) -> str:
        return self.google_oauth_redirect_uri or f"{self.app_base_url.rstrip('/')}/auth/callback"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cookie_secure(self) -> bool:
        return self.app_base_url.startswith("https://")

    @property
    def docs_oauth_scopes(self) -> list[str]:
        return ["https://www.googleapis.com/auth/documents.readonly"]

    def has_oauth_config(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    def has_gcp_config(self) -> bool:
        return bool(self.gcp_project_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()

