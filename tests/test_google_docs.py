import pytest

from app.docs_reader.google_docs import extract_document_id, google_doc_to_markdown
from app.errors import DocumentReadError


def _cell(text: str) -> dict:
    return {"content": [{"paragraph": {"elements": [{"textRun": {"content": text}}]}}]}


def test_extract_document_id_from_google_docs_url():
    document_id = "1AbCdEfGhIjKlMnOpQrStUvWxYz_12345"

    assert (
        extract_document_id(f"https://docs.google.com/document/d/{document_id}/edit")
        == document_id
    )


def test_extract_document_id_rejects_non_docs_url():
    with pytest.raises(DocumentReadError):
        extract_document_id("https://docs.google.com/spreadsheets/d/123/edit")


def test_google_doc_to_markdown_converts_headings_lists_and_tables():
    document = {
        "title": "Proposta IA",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                        "elements": [{"textRun": {"content": "Objetivo\n"}}],
                    }
                },
                {"paragraph": {"elements": [{"textRun": {"content": "Criar assistente.\n"}}]}},
                {
                    "paragraph": {
                        "bullet": {"nestingLevel": 0},
                        "elements": [{"textRun": {"content": "Entregavel 1\n"}}],
                    }
                },
                {
                    "table": {
                        "tableRows": [
                            {
                        "tableCells": [
                                    _cell("Campo\n"),
                                    _cell("Valor\n"),
                                ]
                            },
                            {
                                "tableCells": [
                                    _cell("Prazo\n"),
                                    _cell("30 dias\n"),
                                ]
                            },
                        ]
                    }
                },
            ]
        },
    }

    content = google_doc_to_markdown("doc-id", document)

    assert "# Proposta IA" in content.markdown
    assert "## Objetivo" in content.markdown
    assert "- Entregavel 1" in content.markdown
    assert "| Campo | Valor |" in content.markdown
    assert "| Prazo | 30 dias |" in content.markdown


def test_google_doc_to_markdown_reads_tabs_content():
    document = {
        "title": "Documento com abas",
        "tabs": [
            {
                "tabProperties": {"title": "Principal"},
                "documentTab": {
                    "body": {
                        "content": [
                            {
                                "paragraph": {
                                    "elements": [{"textRun": {"content": "Texto da aba\n"}}]
                                }
                            }
                        ]
                    }
                },
            }
        ],
    }

    content = google_doc_to_markdown("doc-id", document)

    assert "## Aba: Principal" in content.markdown
    assert "Texto da aba" in content.markdown
