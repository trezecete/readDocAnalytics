from __future__ import annotations

import json
import re
from math import ceil

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

    def analyze(self, document: DocumentContent) -> AnalysisReport:
        queries = [
            "objetivo de negocio, problema, resultados esperados",
            "escopo, entregaveis, exclusoes e premissas",
            "dados, fontes, qualidade, permissao de uso e LGPD",
            "modelo de IA, metricas, avaliacao e criterios de aceite",
            "seguranca, integracoes, operacao, custos, monitoramento e suporte",
        ]

        with self.rag.temporary_corpus() as corpus_name:
            self.rag.upload_text(corpus_name, document.markdown, document.title)
            contexts = self.rag.retrieve_contexts(corpus_name, queries)
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
            raise AnalyzerError("Nao foi possivel gerar analise com Gemini.") from exc

        payload = _extract_json(response.text or "")
        try:
            report = AnalysisReport.model_validate(payload)
        except Exception as exc:
            raise AnalyzerError("Gemini retornou um relatorio em formato invalido.") from exc

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
