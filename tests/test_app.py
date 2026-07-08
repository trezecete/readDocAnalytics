from pathlib import Path

from fastapi.testclient import TestClient

from app.analysis.models import AnalysisReport, Finding
from app.docs_reader.models import DocumentContent
from app.main import create_app
from app.web import routes


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_renders_home_page():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Read Doc Analytics" in response.text
    assert "URL do Google Docs" in response.text
    assert "OAuth" not in response.text
    assert "gemini_rag" not in response.text
    assert "documents.readonly" not in response.text


def test_analysis_job_flow_renders_loading_status_and_download(monkeypatch):
    client = TestClient(create_app())
    client.get("/")
    session_id = _current_session_id(client)
    routes.session_store._sessions[session_id]["credentials"] = {
        "token": "token",
        "scopes": ["https://www.googleapis.com/auth/documents.readonly"],
    }

    monkeypatch.setattr(routes, "Thread", ImmediateThread)
    monkeypatch.setattr(routes, "docs_reader", FakeDocsReader())
    monkeypatch.setattr(routes, "build_analyzer", lambda settings: FakeAnalyzer())

    response = client.post(
        "/analysis/jobs",
        data={"document_url": "https://docs.google.com/document/d/example/edit"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    loading_url = response.headers["location"]
    assert loading_url.endswith("/loading")

    job_url = loading_url.removesuffix("/loading")
    status_response = client.get(f"{job_url}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"

    result_response = client.get(job_url)
    assert result_response.status_code == 200
    assert "Baixar relatorio Word" in result_response.text
    assert "gemini_rag" not in result_response.text

    download_response = client.get(f"{job_url}/download.docx")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "attachment;" in download_response.headers["content-disposition"]
    assert download_response.content.startswith(b"PK")


def test_templates_do_not_expose_main_technical_terms():
    for template_name in ["base.html", "index.html", "loading.html", "result.html"]:
        content = (Path(routes.templates.env.loader.searchpath[0]) / template_name).read_text(
            encoding="utf-8"
        )

        assert "OAuth" not in content
        assert "gemini_rag" not in content
        assert "documents.readonly" not in content


def _current_session_id(client: TestClient) -> str:
    signed_id = client.cookies.get(routes.settings.session_cookie_name)
    session_id = routes.session_store._decode_session_id(signed_id)
    assert session_id
    return session_id


class ImmediateThread:
    def __init__(self, target, args=(), daemon=None):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self):
        self.target(*self.args)


class FakeDocsReader:
    def read(self, document_url, credentials):
        return DocumentContent(
            document_id="example",
            title="Proposta Teste",
            markdown=(
                "# Proposta Teste\n\n"
                "A proposta menciona uma base operacional, mas nao define responsavel."
            ),
        )


class FakeAnalyzer:
    def analyze(self, document, progress=None):
        if progress:
            progress("generating_report")
        return AnalysisReport(
            document_title=document.title,
            executive_summary="A proposta precisa confirmar dados e criterios de aceite.",
            findings=[
                Finding(
                    title="Base de dados sem responsavel definido",
                    category="Dados",
                    severity="alta",
                    finding_type="risco",
                    evidence="A proposta menciona uma base operacional.",
                    explanation="Sem responsavel, o acesso aos dados pode atrasar o projeto.",
                    recommendation="Definir responsavel e permissao de uso antes do inicio.",
                    confidence="alta",
                )
            ],
            recommendations=["Confirmar responsavel pelos dados."],
            limitations=["Imagens nao foram analisadas."],
            analyzer_backend="local",
        )
