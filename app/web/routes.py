from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from app.analysis import build_analyzer
from app.analysis.models import AnalysisReport
from app.auth import CredentialsData, GoogleOAuthClient, SessionStore
from app.config import get_settings
from app.docs_reader import GoogleDocsReader
from app.errors import UserFacingError

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

settings = get_settings()
session_store = SessionStore(settings)
oauth_client = GoogleOAuthClient(settings)
docs_reader = GoogleDocsReader()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    session = session_store.get_or_create(request)
    response = templates.TemplateResponse(
        request,
        "index.html",
        _template_context(request, session.data),
    )
    if session.is_new:
        session_store.save(response, session)
    return response


@router.get("/auth/login")
def login(request: Request):
    session = session_store.get_or_create(request)
    state = uuid4().hex
    session.data["oauth_state"] = state
    try:
        authorization_url = oauth_client.authorization_url(state)
    except UserFacingError as exc:
        return _render_index(request, session, exc.message, status_code=exc.status_code)
    response = RedirectResponse(authorization_url, status_code=302)
    session_store.save(response, session)
    return response


@router.get("/auth/callback")
def auth_callback(request: Request, state: str | None = None):
    session = session_store.get_or_create(request)
    expected_state = session.data.get("oauth_state")
    if not state or state != expected_state:
        return _render_index(
            request,
            session,
            "Falha ao validar o retorno OAuth. Tente fazer login novamente.",
            status_code=400,
        )

    authorization_response = f"{settings.oauth_redirect_uri}?{request.url.query}"
    try:
        credentials = oauth_client.fetch_credentials(authorization_response)
    except UserFacingError as exc:
        return _render_index(request, session, exc.message, status_code=exc.status_code)

    session.data.pop("oauth_state", None)
    session.data["credentials"] = credentials.model_dump(mode="json")
    response = RedirectResponse("/", status_code=302)
    session_store.save(response, session)
    return response


@router.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, document_url: str = Form(...)):
    session = session_store.get_or_create(request)
    credentials_payload = session.data.get("credentials")
    if not credentials_payload:
        return _render_index(
            request,
            session,
            "Faca login com Google antes de analisar um documento privado.",
            status_code=401,
        )

    try:
        credentials = CredentialsData.model_validate(credentials_payload)
        document = await run_in_threadpool(docs_reader.read, document_url, credentials)
        if document.char_count > settings.max_document_chars:
            raise UserFacingError(
                f"Documento excede o limite de {settings.max_document_chars} caracteres.",
                status_code=413,
            )
        analyzer = build_analyzer(settings)
        report: AnalysisReport = await run_in_threadpool(analyzer.analyze, document)
    except UserFacingError as exc:
        return _render_index(request, session, exc.message, status_code=exc.status_code)

    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            **_template_context(request, session.data),
            "document": document,
            "report": report,
            "report_json": report.model_dump_json(indent=2),
            "report_markdown": _report_to_markdown(report),
        },
    )
    session_store.save(response, session)
    return response


@router.post("/auth/logout")
def logout(request: Request):
    session = session_store.get_or_create(request)
    response = RedirectResponse("/", status_code=302)
    session_store.destroy(response, session)
    return response


def _render_index(
    request: Request,
    session,
    error: str,
    status_code: int = 400,
):
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            **_template_context(request, session.data),
            "error": error,
        },
        status_code=status_code,
    )
    session_store.save(response, session)
    return response


def _template_context(request: Request, session_data: dict) -> dict:
    oauth_ready = settings.has_oauth_config()
    gcp_ready = settings.has_gcp_config()
    return {
        "request": request,
        "authenticated": bool(session_data.get("credentials")),
        "oauth_ready": oauth_ready,
        "gcp_ready": gcp_ready,
        "analyzer_backend": settings.analyzer_backend,
        "oauth_scope": settings.docs_oauth_scopes[0],
        "setup_warnings": _setup_warnings(oauth_ready, gcp_ready),
    }


def _setup_warnings(oauth_ready: bool, gcp_ready: bool) -> list[str]:
    warnings: list[str] = []
    if not oauth_ready:
        warnings.append("Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET para usar login Google.")
    if settings.analyzer_backend == "gemini_rag" and not gcp_ready:
        warnings.append("Configure GCP_PROJECT_ID para ativar RAG Engine e Gemini.")
    if settings.analyzer_backend == "local":
        warnings.append(
            "ANALYZER_BACKEND=local esta ativo; a analise usa heuristicas de prototipo."
        )
    return warnings


def _report_to_markdown(report: AnalysisReport) -> str:
    lines = [
        f"# Relatorio de analise: {report.document_title}",
        "",
        "## Resumo executivo",
        "",
        report.executive_summary,
        "",
        "## Achados",
        "",
    ]
    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.title}",
                "",
                f"- Categoria: {finding.category}",
                f"- Severidade: {finding.severity}",
                f"- Tipo: {finding.finding_type}",
                f"- Confianca: {finding.confidence}",
            ]
        )
        if finding.evidence:
            lines.append(f"- Evidencia: {finding.evidence}")
        lines.extend(
            [
                f"- Explicacao: {finding.explanation}",
                f"- Recomendacao: {finding.recommendation}",
                "",
            ]
        )

    lines.extend(["## Recomendacoes gerais", ""])
    lines.extend(f"- {item}" for item in report.recommendations)
    lines.extend(["", "## Limitacoes", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    return "\n".join(lines).strip()
