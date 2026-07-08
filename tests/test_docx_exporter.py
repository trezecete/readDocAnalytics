from app.analysis.models import AnalysisCoverage, AnalysisReport, Finding
from app.reports import build_docx_report


def test_build_docx_report_returns_word_document_bytes():
    report = _sample_report()

    content = build_docx_report(report)

    assert content.startswith(b"PK")
    assert len(content) > 1_000


def _sample_report() -> AnalysisReport:
    return AnalysisReport(
        document_title="Proposta Teste",
        executive_summary="Foram encontrados riscos e lacunas que precisam de decisao.",
        findings=[
            Finding(
                title="Base de dados sem dono definido",
                category="Dados",
                severity="alta",
                finding_type="risco",
                evidence="A proposta menciona a base operacional sem indicar responsavel.",
                explanation="Sem dono da base, o projeto pode atrasar na fase de acesso.",
                recommendation="Definir responsavel, permissao de uso e plano de acesso aos dados.",
                confidence="alta",
            ),
            Finding(
                title="Metricas de aceite ausentes",
                category="Avaliacao",
                severity="media",
                finding_type="lacuna",
                explanation="Nao ha criterio objetivo para aprovar a qualidade do modelo.",
                recommendation="Definir metricas, baseline e limiar minimo de aceite.",
                confidence="media",
            ),
        ],
        recommendations=["Confirmar responsaveis e criterios antes de aprovar."],
        limitations=["Comentarios e imagens nao foram analisados nesta versao."],
        analyzer_backend="gemini_rag",
        coverage=AnalysisCoverage(
            mode_label="Analise aprofundada com IA",
            completeness_level="rag_assistida",
            document_chars=12_000,
            document_bytes=14_000,
            text_scanned_percent=100,
            estimated_chunks=4,
            categories_checked=["Dados", "Avaliacao"],
            evidence_policy="Riscos usam evidencia textual.",
            caveat="Revisao automatizada nao substitui validacao humana.",
        ),
    )
