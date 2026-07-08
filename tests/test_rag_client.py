import json

import pytest

from app.config import Settings
from app.errors import ConfigurationError
from app.rag.client import RagEngineClient


def test_rag_client_rejects_oauth_client_json_as_adc(tmp_path):
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"web": {"client_id": "abc"}}), encoding="utf-8")

    settings = Settings(
        gcp_project_id="project",
        google_application_credentials=str(credentials_path),
    )

    with pytest.raises(ConfigurationError, match="OAuth Client JSON"):
        RagEngineClient(settings)

