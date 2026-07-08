from app.analysis.local import LocalHeuristicAnalyzer
from app.docs_reader.models import DocumentContent


def test_local_analyzer_flags_missing_core_sections():
    document = DocumentContent(
        document_id="doc",
        title="Proposta curta",
        markdown="Queremos criar um chatbot urgente para atendimento.",
    )

    report = LocalHeuristicAnalyzer().analyze(document)

    categories = {finding.category for finding in report.findings}
    assert "Dados" in categories
    assert "Privacidade" in categories
    assert any(finding.finding_type == "risco" for finding in report.findings)
    assert report.analyzer_backend == "local"


def test_local_analyzer_does_not_require_evidence_for_gaps():
    document = DocumentContent(
        document_id="doc",
        title="Sem dados",
        markdown="Objetivo: melhorar atendimento. Escopo: prototipo.",
    )

    report = LocalHeuristicAnalyzer().analyze(document)
    gaps = [finding for finding in report.findings if finding.finding_type == "lacuna"]

    assert gaps
    assert all(finding.evidence is None for finding in gaps)

