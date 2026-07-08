import os

import pytest

from app.config import Settings
from app.errors import AnalyzerError
from app.rag.client import RagEngineClient, _raise_rag_error


def test_rag_client_exports_google_application_credentials(monkeypatch, tmp_path):
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text('{"type": "service_account"}', encoding="utf-8")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    settings = Settings(
        gcp_project_id="project",
        google_application_credentials=str(credentials_path),
    )

    RagEngineClient(settings)

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(credentials_path.resolve())


def test_rag_timeout_error_is_user_facing():
    settings = Settings(gcp_project_id="project", gcp_location="europe-west4")

    with pytest.raises(AnalyzerError) as exc_info:
        _raise_rag_error(
            "criar corpus temporario",
            settings,
            TimeoutError("Operation x did not complete within the timeout of 300 seconds."),
        )

    assert "excedeu o tempo limite" in exc_info.value.message


def test_rag_internal_error_suggests_region_retry():
    settings = Settings(gcp_project_id="project", gcp_location="europe-west4")

    with pytest.raises(AnalyzerError) as exc_info:
        _raise_rag_error(
            "criar corpus temporario",
            settings,
            RuntimeError("{'code': 13, 'message': 'INTERNAL'}"),
        )

    assert "erro interno" in exc_info.value.message
    assert "europe-west3" in exc_info.value.message
