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
    assert report.coverage is not None
    assert report.coverage.completeness_level == "triagem"
    assert report.coverage.text_scanned_percent == 100.0


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


def test_local_analyzer_reports_document_coverage():
    document = DocumentContent(
        document_id="doc",
        title="Proposta longa",
        markdown="Objetivo: automatizar indicadores.\n" * 500,
    )

    report = LocalHeuristicAnalyzer().analyze(document)

    assert report.coverage is not None
    assert report.coverage.document_chars == document.char_count
    assert report.coverage.document_bytes == document.byte_count
    assert report.coverage.estimated_chunks > 1
