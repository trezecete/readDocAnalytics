import pytest

from app.analysis.gemini_rag import (
    _extract_json,
    _normalize_report_payload,
    _raise_gemini_error,
)
from app.config import Settings
from app.errors import AnalyzerError


def test_extract_json_accepts_fenced_json():
    payload = _extract_json('```json\n{"ok": true}\n```')

    assert payload == {"ok": True}


def test_gemini_not_found_error_mentions_model_and_region():
    settings = Settings(
        gcp_project_id="project",
        gcp_location="europe-west3",
        gemini_model="gemini-3.5-flash",
    )

    with pytest.raises(AnalyzerError) as exc_info:
        _raise_gemini_error(
            settings,
            RuntimeError("404 NOT_FOUND. Publisher model was not found."),
        )

    assert "gemini-3.5-flash" in exc_info.value.message
    assert "europe-west3" in exc_info.value.message
    assert "gemini-2.5-flash" in exc_info.value.message


def test_normalize_report_payload_maps_common_model_variants():
    payload = {
        "document_title": "Doc",
        "executive_summary": "Resumo",
        "findings": [
            {
                "title": "Info",
                "category": "Resumo",
                "severity": "média",
                "finding_type": "informativa",
                "explanation": "Explicacao suficientemente longa.",
                "recommendation": "Recomendacao suficientemente longa.",
                "confidence": "médio",
            }
        ],
    }

    normalized = _normalize_report_payload(payload)

    assert normalized["analyzer_backend"] == "gemini_rag"
    assert normalized["findings"][0]["severity"] == "media"
    assert normalized["findings"][0]["finding_type"] == "recomendacao"
    assert normalized["findings"][0]["confidence"] == "media"
