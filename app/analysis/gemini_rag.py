from __future__ import annotations

import json
import re
from collections.abc import Callable
from math import ceil
from typing import Any
from unicodedata import normalize

from app.analysis.models import AnalysisCoverage, AnalysisReport
from app.config import Settings
from app.docs_reader.models import DocumentContent
from app.errors import AnalyzerError
from app.rag import RagEngineClient
from app.rag.client import RetrievedContext


class GeminiRagAnalyzer:
    backend_name = "gemini_rag"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.rag = RagEngineClient(settings)

    def analyze(
        self,
        document: DocumentContent,
        progress: Callable[[str], None] | None = None,
    ) -> AnalysisReport:
        queries = [
            "objetivo de negocio, problema, resultados esperados",
            "escopo, entregaveis, exclusoes e premissas",
            "dados, fontes, qualidade, permissao de uso e LGPD",
            "modelo de IA, metricas, avaliacao e criterios de aceite",
            "seguranca, integracoes, operacao, custos, monitoramento e suporte",
        ]

        _notify_progress(progress, "preparing_context")
        with self.rag.temporary_corpus() as corpus_name:
            self.rag.upload_text(corpus_name, document.markdown, document.title)
            _notify_progress(progress, "retrieving_evidence")
            contexts = self.rag.retrieve_contexts(corpus_name, queries)
            _notify_progress(progress, "generating_report")
            report = self._generate_report(document, contexts)
            return report.model_copy(
                update={
                    "coverage": AnalysisCoverage(
                        mode_label="Analise assistida por RAG Engine e Gemini",
                        completeness_level="rag_assistida",
                        document_chars=document.char_count,
                        document_bytes=document.byte_count,
                        text_scanned_percent=100.0,
                        estimated_chunks=max(
                            1,
                            ceil(document.char_count / self.settings.rag_chunk_size),
                        ),
                        categories_checked=[
                            "Objetivo",
                            "Escopo",
                            "Dados",
                            "Privacidade",
                            "Avaliacao",
                            "Aceite",
                            "Custos",
                            "Operacao",
                            "Seguranca",
                        ],
                        evidence_policy=(
                            "O documento normalizado foi enviado ao RAG; o Gemini recebeu "
                            f"{len(contexts)} trechos recuperados por consultas tematicas."
                        ),
                        caveat=(
                            "RAG aumenta cobertura e rastreabilidade, mas ainda exige revisao "
                            "humana para aprovar proposta tecnica."
                        ),
                    )
                }
            )

    def _generate_report(
        self,
        document: DocumentContent,
        contexts: list[RetrievedContext],
    ) -> AnalysisReport:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise AnalyzerError("SDK google-genai nao esta instalado.") from exc

        try:
            client = genai.Client(
                enterprise=True,
                project=self.settings.gcp_project_id,
                location=self.settings.gcp_location,
            )
        except TypeError:
            client = genai.Client(
                vertexai=True,
                project=self.settings.gcp_project_id,
                location=self.settings.gcp_location,
            )

        prompt = self._build_prompt(document, contexts)
        try:
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            _raise_gemini_error(self.settings, exc)

        if not response.text:
            raise AnalyzerError(
                "Gemini nao retornou texto analisavel. Tente novamente ou reduza o documento."
            )

        payload = _normalize_report_payload(_extract_json(response.text))
        try:
            report = AnalysisReport.model_validate(payload)
        except Exception as exc:
            raise AnalyzerError(
                "Gemini retornou um relatorio em formato invalido mesmo apos normalizacao."
            ) from exc

        return report.model_copy(update={"analyzer_backend": self.backend_name})

    def _build_prompt(self, document: DocumentContent, contexts: list[RetrievedContext]) -> str:
        context_block = "\n\n".join(
            f"Consulta: {item.query}\nTrecho: {item.text}" for item in contexts
        )
        return f"""
Voce e um revisor tecnico de propostas de projetos de IA.
Analise apenas o contexto recuperado do documento. Nao invente fatos.

Documento: {document.title}

Contexto recuperado pelo RAG:
{context_block}

Gere um JSON valido com este formato:
{{
  "document_title": "{document.title}",
  "executive_summary": "Resumo curto e objetivo.",
  "findings": [
    {{
      "title": "Titulo do achado",
      "category": "Objetivo|Escopo|Dados|Privacidade|Avaliacao|Custos|Operacao|Seguranca",
      "severity": "critica|alta|media|baixa|informativa",
      "finding_type": "risco|inconsistencia|lacuna|recomendacao",
      "evidence": "Trecho textual que sustenta o achado, ou null quando for lacuna",
      "explanation": "Por que isso importa",
      "recommendation": "Como corrigir ou mitigar",
      "confidence": "alta|media|baixa"
    }}
  ],
  "recommendations": ["acao objetiva"],
  "limitations": ["limite da analise"],
  "analyzer_backend": "gemini_rag"
}}

Regras:
- Achados do tipo risco e inconsistencia exigem evidencia literal do contexto.
- O campo finding_type aceita somente: risco, inconsistencia, lacuna ou recomendacao.
- Nao use finding_type=informativa; informativa e apenas uma severidade possivel.
- Se uma informacao importante nao aparece, classifique como lacuna e use evidence=null.
- Priorize riscos de dados, LGPD, escopo, metricas, custos, seguranca e operacao.
- Nao inclua texto fora do JSON.
""".strip()


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AnalyzerError("Resposta do modelo nao continha JSON valido.") from exc
    if not isinstance(payload, dict):
        raise AnalyzerError("Resposta do modelo precisa ser um objeto JSON.")
    return payload


def _normalize_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("recommendations", [])
    payload.setdefault("limitations", [])
    payload.setdefault("analyzer_backend", "gemini_rag")

    findings = payload.get("findings")
    if not isinstance(findings, list):
        payload["findings"] = []
        return payload

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        finding["severity"] = _coerce_label(
            finding.get("severity"),
            {
                "critico": "critica",
                "critica": "critica",
                "alta": "alta",
                "alto": "alta",
                "media": "media",
                "medio": "media",
                "baixa": "baixa",
                "baixo": "baixa",
                "informativo": "informativa",
                "informativa": "informativa",
                "info": "informativa",
            },
            "media",
        )
        finding["finding_type"] = _coerce_label(
            finding.get("finding_type"),
            {
                "risco": "risco",
                "risk": "risco",
                "inconsistencia": "inconsistencia",
                "inconsistency": "inconsistencia",
                "lacuna": "lacuna",
                "gap": "lacuna",
                "ausencia": "lacuna",
                "recomendacao": "recomendacao",
                "recommendation": "recomendacao",
                "informativa": "recomendacao",
                "informativo": "recomendacao",
                "info": "recomendacao",
            },
            "lacuna",
        )
        finding["confidence"] = _coerce_label(
            finding.get("confidence"),
            {
                "alta": "alta",
                "alto": "alta",
                "media": "media",
                "medio": "media",
                "baixa": "baixa",
                "baixo": "baixa",
            },
            "media",
        )
    return payload


def _coerce_label(value: Any, aliases: dict[str, str], default: str) -> str:
    key = _normalize_label(value)
    return aliases.get(key, default)


def _notify_progress(progress: Callable[[str], None] | None, stage: str) -> None:
    if progress:
        progress(stage)


def _normalize_label(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    text = normalize("NFKD", text)
    text = "".join(character for character in text if ord(character) < 128)
    return text


def _raise_gemini_error(settings: Settings, exc: Exception):
    message = str(exc)
    normalized = message.lower()

    if "404" in normalized or "not_found" in normalized or "was not found" in normalized:
        raise AnalyzerError(
            f"O modelo `{settings.gemini_model}` nao esta disponivel ou nao esta acessivel "
            f"na regiao `{settings.gcp_location}` para o projeto `{settings.gcp_project_id}`. "
            "Use `GEMINI_MODEL=gemini-2.5-flash` com `GCP_LOCATION=europe-west3`, ou escolha "
            "um modelo disponivel nessa regiao no Vertex AI."
        ) from exc

    if "permission" in normalized or "403" in normalized or "unauthorized" in normalized:
        raise AnalyzerError(
            "Sem permissao para chamar Gemini no Vertex AI. Confirme que a service account "
            "tem `roles/aiplatform.user` e que a Vertex AI API esta habilitada."
        ) from exc

    if "quota" in normalized or "429" in normalized or "rate" in normalized:
        raise AnalyzerError(
            "Gemini recusou a chamada por limite de quota ou taxa. Aguarde alguns minutos ou "
            "verifique as quotas do modelo/regiao no Vertex AI."
        ) from exc

    detail = _safe_error_detail(message)
    raise AnalyzerError(
        f"Nao foi possivel gerar analise com Gemini. Detalhe tecnico: {detail}"
    ) from exc


def _safe_error_detail(message: str, limit: int = 500) -> str:
    compact = " ".join(message.split())
    return compact[:limit] if compact else "erro sem detalhe retornado pelo SDK"
