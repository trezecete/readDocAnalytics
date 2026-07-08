from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.analysis.models import AnalysisReport, Finding

SEVERITY_LABELS = {
    "critica": "Crítico",
    "alta": "Alto",
    "media": "Médio",
    "baixa": "Baixo",
    "informativa": "Informativo",
}

FINDING_TYPE_LABELS = {
    "risco": "Risco",
    "inconsistencia": "Inconsistência",
    "lacuna": "Lacuna",
    "recomendacao": "Recomendação",
}

SEVERITY_ORDER = ["critica", "alta", "media", "baixa", "informativa"]


@dataclass(frozen=True)
class ReportPresenter:
    report: AnalysisReport
    grouped_findings: dict[str, list[Finding]]
    priority_findings: list[Finding]
    gap_findings: list[Finding]
    evidence_findings: list[Finding]
    severity_counts: dict[str, int]
    severity_labels: dict[str, str]
    finding_type_labels: dict[str, str]
    severity_order: list[str]
    primary_next_step: str
    mode_label: str


def build_report_presenter(report: AnalysisReport) -> ReportPresenter:
    grouped: dict[str, list[Finding]] = defaultdict(list)
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in report.findings:
        grouped[finding.severity].append(finding)
        counts[finding.severity] += 1

    priority = [
        finding
        for severity in ("critica", "alta")
        for finding in grouped.get(severity, [])
    ]
    gaps = [finding for finding in report.findings if finding.finding_type == "lacuna"]
    evidence = [finding for finding in report.findings if finding.evidence]
    mode_label = "Análise aprofundada com IA"
    if report.analyzer_backend == "local":
        mode_label = "Triagem rápida"

    return ReportPresenter(
        report=report,
        grouped_findings=dict(grouped),
        priority_findings=priority,
        gap_findings=gaps,
        evidence_findings=evidence,
        severity_counts=counts,
        severity_labels=SEVERITY_LABELS,
        finding_type_labels=FINDING_TYPE_LABELS,
        severity_order=SEVERITY_ORDER,
        primary_next_step=_primary_next_step(report, priority, gaps),
        mode_label=mode_label,
    )


def report_to_markdown(report: AnalysisReport) -> str:
    presenter = build_report_presenter(report)
    lines = [
        f"# Relatório executivo: {report.document_title}",
        "",
        "## Resumo da proposta",
        "",
        report.executive_summary,
        "",
        "## Principais pontos de atenção",
        "",
        f"- Modo: {presenter.mode_label}",
        f"- Achados críticos: {presenter.severity_counts['critica']}",
        f"- Achados altos: {presenter.severity_counts['alta']}",
        f"- Lacunas para decisão: {len(presenter.gap_findings)}",
        f"- Próximo passo recomendado: {presenter.primary_next_step}",
        "",
    ]

    if report.coverage:
        lines.extend(
            [
                "## Como a análise foi conduzida",
                "",
                f"- Documento lido: {report.coverage.document_chars} caracteres",
                f"- Texto analisado: {report.coverage.text_scanned_percent:.0f}%",
                "- Categorias verificadas: "
                + ", ".join(report.coverage.categories_checked),
                f"- Observação: {report.coverage.caveat}",
                "",
            ]
        )

    for severity in SEVERITY_ORDER:
        findings = presenter.grouped_findings.get(severity, [])
        if not findings:
            continue
        lines.extend([f"## {SEVERITY_LABELS[severity]}", ""])
        for finding in findings:
            lines.extend(_finding_markdown(finding))

    lines.extend(["## Plano de ação recomendado", ""])
    lines.extend(f"- {item}" for item in report.recommendations)
    lines.extend(["", "## Limitações da análise", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    return "\n".join(lines).strip()


def _finding_markdown(finding: Finding) -> list[str]:
    lines = [
        f"### {finding.title}",
        "",
        f"- Categoria: {finding.category}",
        f"- Tipo: {FINDING_TYPE_LABELS[finding.finding_type]}",
        f"- Confiança: {finding.confidence}",
    ]
    if finding.evidence:
        lines.append(f"- Evidência: {finding.evidence}")
    lines.extend(
        [
            f"- Por que importa: {finding.explanation}",
            f"- Ação sugerida: {finding.recommendation}",
            "",
        ]
    )
    return lines


def _primary_next_step(
    report: AnalysisReport,
    priority: list[Finding],
    gaps: list[Finding],
) -> str:
    if priority:
        return "Tratar os riscos críticos e altos antes de aprovar a proposta."
    if gaps:
        return "Completar as lacunas de informação antes da decisão."
    if report.recommendations:
        return report.recommendations[0]
    return "Revisar os achados com os responsáveis pela proposta."
