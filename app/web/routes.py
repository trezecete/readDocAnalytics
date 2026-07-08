from __future__ import annotations

from threading import Thread
from unicodedata import normalize
from uuid import uuid4

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.analysis import build_analyzer
from app.auth import CredentialsData, GoogleOAuthClient, SessionStore
from app.config import get_settings
from app.docs_reader import GoogleDocsReader
from app.errors import UserFacingError
from app.jobs import AnalysisJob, JobStage, JobStatus, JobStore
from app.reports import build_docx_report, build_report_presenter, report_to_markdown

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

settings = get_settings()
session_store = SessionStore(settings)
oauth_client = GoogleOAuthClient(settings)
docs_reader = GoogleDocsReader()
job_store = JobStore()


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
        authorization_url, code_verifier = oauth_client.authorization_url(state)
    except UserFacingError as exc:
        return _render_index(request, session, exc.message, status_code=exc.status_code)
    session.data["oauth_code_verifier"] = code_verifier
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
            "Não conseguimos validar o retorno do Google. Tente entrar novamente.",
            status_code=400,
        )

    authorization_response = f"{settings.oauth_redirect_uri}?{request.url.query}"
    try:
        credentials = oauth_client.fetch_credentials(
            authorization_response,
            session.data.get("oauth_code_verifier"),
        )
    except UserFacingError as exc:
        return _render_index(request, session, exc.message, status_code=exc.status_code)

    session.data.pop("oauth_state", None)
    session.data.pop("oauth_code_verifier", None)
    session.data["credentials"] = credentials.model_dump(mode="json")
    response = RedirectResponse("/", status_code=302)
    session_store.save(response, session)
    return response


@router.post("/analysis/jobs")
def create_analysis_job(request: Request, document_url: str = Form(...)):
    session = session_store.get_or_create(request)
    credentials_payload = session.data.get("credentials")
    if not credentials_payload:
        return _render_index(
            request,
            session,
            "Entre com sua conta Google para liberar a leitura do documento.",
            status_code=401,
        )

    job = job_store.create(
        session_id=session.session_id,
        document_url=document_url,
        credentials_payload=credentials_payload,
    )
    Thread(target=_run_analysis_job, args=(job,), daemon=True).start()

    response = RedirectResponse(f"/analysis/jobs/{job.job_id}/loading", status_code=303)
    session_store.save(response, session)
    return response


@router.post("/analyze")
def legacy_analyze(request: Request, document_url: str = Form(...)):
    return create_analysis_job(request, document_url)


@router.get("/analysis/jobs/{job_id}/loading", response_class=HTMLResponse)
def loading(request: Request, job_id: str):
    session = session_store.get_or_create(request)
    job = _get_authorized_job(job_id, session.session_id)
    if not job:
        return _render_index(
            request,
            session,
            "Não encontramos essa análise. Comece uma nova revisão.",
            status_code=404,
        )

    response = templates.TemplateResponse(
        request,
        "loading.html",
        {
            **_template_context(request, session.data),
            "job": job,
        },
    )
    session_store.save(response, session)
    return response


@router.get("/analysis/jobs/{job_id}/status")
def job_status(request: Request, job_id: str):
    session = session_store.get_or_create(request)
    job = _get_authorized_job(job_id, session.session_id)
    if not job:
        return JSONResponse(
            {"status": JobStatus.FAILED.value, "error": "Análise não encontrada."},
            status_code=404,
        )
    return job.snapshot()


@router.get("/analysis/jobs/{job_id}", response_class=HTMLResponse)
def job_result(request: Request, job_id: str):
    session = session_store.get_or_create(request)
    job = _get_authorized_job(job_id, session.session_id)
    if not job:
        return _render_index(
            request,
            session,
            "Não encontramos essa análise. Comece uma nova revisão.",
            status_code=404,
        )
    if job.status == JobStatus.FAILED:
        return _render_index(
            request,
            session,
            job.error or "Não foi possível concluir a análise.",
            status_code=400,
        )
    if job.status != JobStatus.COMPLETED or not job.report:
        return RedirectResponse(f"/analysis/jobs/{job.job_id}/loading", status_code=302)

    presenter = build_report_presenter(job.report)
    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            **_template_context(request, session.data),
            "document": job.document,
            "job": job,
            "report": job.report,
            "presenter": presenter,
            "report_markdown": report_to_markdown(job.report),
        },
    )
    session_store.save(response, session)
    return response


@router.get("/analysis/jobs/{job_id}/download.docx")
def download_docx(request: Request, job_id: str):
    session = session_store.get_or_create(request)
    job = _get_authorized_job(job_id, session.session_id)
    if not job or job.status != JobStatus.COMPLETED or not job.report:
        return JSONResponse(
            {"error": "Relatório ainda não está pronto para download."},
            status_code=404,
        )

    content = build_docx_report(job.report)
    filename = _safe_filename(job.report.document_title) + ".docx"
    return Response(
        content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/auth/logout")
def logout(request: Request):
    session = session_store.get_or_create(request)
    response = RedirectResponse("/", status_code=302)
    session_store.destroy(response, session)
    return response


def _run_analysis_job(job: AnalysisJob) -> None:
    try:
        job.start()
        credentials = CredentialsData.model_validate(job.credentials_payload)

        job.set_stage(JobStage.READING)
        document = docs_reader.read(job.document_url, credentials)
        if document.byte_count > settings.max_document_bytes:
            raise UserFacingError(
                (
                    "O documento é maior do que o limite atual de "
                    f"{_format_bytes(settings.max_document_bytes)} após a organização do texto."
                ),
                status_code=413,
            )

        job.set_document(document, settings.analyzer_backend)
        job.set_stage(JobStage.ORGANIZING)

        analyzer = build_analyzer(settings)
        report = analyzer.analyze(document, progress=lambda stage: _update_job_stage(job, stage))

        job.set_stage(JobStage.FINALIZING)
        job.complete(report)
    except UserFacingError as exc:
        job.fail(exc.message)
    except Exception:
        job.fail("A análise não foi concluída. Tente novamente em alguns minutos.")


def _get_authorized_job(job_id: str, session_id: str) -> AnalysisJob | None:
    job = job_store.get(job_id)
    if not job or job.session_id != session_id:
        return None
    return job


def _update_job_stage(job: AnalysisJob, stage_name: str) -> None:
    try:
        job.set_stage(JobStage(stage_name))
    except ValueError:
        return


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
    analysis_mode = "Análise aprofundada com IA"
    if settings.analyzer_backend == "local":
        analysis_mode = "Triagem rápida"

    return {
        "request": request,
        "authenticated": bool(session_data.get("credentials")),
        "oauth_ready": oauth_ready,
        "gcp_ready": gcp_ready,
        "analysis_mode": analysis_mode,
        "document_limit_label": _format_bytes(settings.max_document_bytes),
        "setup_warnings": _setup_warnings(oauth_ready, gcp_ready),
    }


def _setup_warnings(oauth_ready: bool, gcp_ready: bool) -> list[str]:
    warnings: list[str] = []
    if not oauth_ready:
        warnings.append(
            "Configure a conexão com Google para permitir que o usuário leia documentos privados."
        )
    if settings.analyzer_backend == "gemini_rag" and not gcp_ready:
        warnings.append("Configure o projeto Google Cloud para ativar a análise aprofundada.")
    if settings.analyzer_backend == "gemini_rag" and settings.gcp_location in {
        "us-central1",
        "us-east1",
        "us-east4",
    }:
        warnings.append(
            "A região de nuvem configurada pode exigir liberação especial. "
            "Use europe-west3 para este protótipo."
        )
    if settings.analyzer_backend == "local":
        warnings.append(
            "Modo de triagem rápida ativo. Para uma revisão mais profunda, ative a análise com IA."
        )
    return warnings


def _safe_filename(value: str) -> str:
    normalized = normalize("NFKD", value)
    ascii_value = "".join(character for character in normalized if ord(character) < 128)
    safe = "".join(
        character for character in ascii_value if character.isalnum() or character in " -_"
    )
    safe = "-".join(safe.strip().split())
    return safe[:80] or "relatorio-analise"


def _format_bytes(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} MB"
    if value >= 1_000:
        return f"{value / 1_000:.1f} KB"
    return f"{value} bytes"
