from __future__ import annotations

import re

from app.analysis.models import AnalysisReport, Finding
from app.docs_reader.models import DocumentContent


class LocalHeuristicAnalyzer:
    """Deterministic fallback for local demos and tests.

    It is intentionally conservative: it flags missing proposal sections as gaps and avoids
    making factual claims that are not supported by the submitted text.
    """

    backend_name = "local"

    def analyze(self, document: DocumentContent) -> AnalysisReport:
        text = document.markdown
        findings: list[Finding] = []

        findings.extend(self._missing_section_findings(text))
        findings.extend(self._risk_keyword_findings(text))

        if not findings:
            findings.append(
                Finding(
                    title="Proposta com estrutura basica identificada",
                    category="Resumo",
                    severity="informativa",
                    finding_type="recomendacao",
                    explanation=(
                        "O analisador local encontrou sinais das secoes principais, mas a revisao "
                        "com Gemini/RAG ainda e recomendada para uma avaliacao mais profunda."
                    ),
                    recommendation=(
                        "Ative ANALYZER_BACKEND=gemini_rag quando as credenciais GCP estiverem "
                        "configuradas."
                    ),
                    confidence="media",
                )
            )

        return AnalysisReport(
            document_title=document.title,
            executive_summary=self._build_summary(findings),
            findings=findings,
            recommendations=[
                "Completar as lacunas criticas antes de aprovar o desenvolvimento.",
                "Manter cada risco vinculado a evidencia textual e a uma acao de mitigacao.",
                "Revisar custos, dados, privacidade e criterios de aceite com os responsaveis.",
            ],
            limitations=[
                (
                    "Este modo local usa heuristicas deterministicas e nao substitui a revisao "
                    "Gemini/RAG."
                ),
                "Imagens, comentarios e sugestoes do Google Docs nao sao analisados nesta versao.",
            ],
            analyzer_backend=self.backend_name,
        )

    def _missing_section_findings(self, text: str) -> list[Finding]:
        checks = [
            (
                "Objetivo de negocio pouco explicito",
                "Objetivo",
                "alta",
                [r"\bobjetivo\b", r"\bproblema\b", r"\bmeta\b"],
                (
                    "A proposta nao apresenta de forma clara o objetivo de negocio ou problema "
                    "a resolver."
                ),
                (
                    "Adicionar uma secao de objetivo com problema, publico afetado e resultado "
                    "esperado."
                ),
            ),
            (
                "Escopo e entregaveis podem estar incompletos",
                "Escopo",
                "alta",
                [r"\bescopo\b", r"\bentregavel\b", r"\bentrega\b"],
                "A proposta nao deixa evidente o que sera entregue e o que fica fora do projeto.",
                "Definir entregaveis, exclusoes de escopo e responsabilidades por fase.",
            ),
            (
                "Dados necessarios nao estao especificados",
                "Dados",
                "critica",
                [r"\bdado", r"\bdataset\b", r"\bbase\b", r"\bfonte\b"],
                (
                    "Projetos de IA dependem de dados; a proposta nao descreve fontes, "
                    "qualidade ou acesso."
                ),
                "Informar fontes de dados, proprietarios, qualidade, volume, acesso e restricoes.",
            ),
            (
                "Privacidade e LGPD nao aparecem na proposta",
                "Privacidade",
                "critica",
                [r"\blgpd\b", r"\bprivacidade\b", r"\bdados pessoais\b", r"\bconsentimento\b"],
                "Nao ha sinal claro de avaliacao de privacidade ou tratamento de dados pessoais.",
                "Adicionar avaliacao LGPD, classificacao dos dados e medidas de minimizacao.",
            ),
            (
                "Metricas de avaliacao do modelo nao foram definidas",
                "Avaliacao",
                "alta",
                [r"\bmetrica\b", r"\bavaliacao\b", r"\bacuracia\b", r"\bprecisao\b", r"\bf1\b"],
                "Sem metricas, nao ha criterio objetivo para saber se o modelo de IA funciona.",
                "Definir metricas tecnicas, baseline, conjunto de validacao e limiar de aceite.",
            ),
            (
                "Criterios de aceite nao estao claros",
                "Aceite",
                "media",
                [r"\bcriterio de aceite\b", r"\baceite\b", r"\bvalidacao\b"],
                "A proposta nao deixa claro como o projeto sera considerado concluido.",
                "Escrever criterios de aceite verificaveis por entregavel.",
            ),
            (
                "Custos e operacao nao foram detalhados",
                "Custos",
                "media",
                [r"\bcusto\b", r"\borcamento\b", r"\bbudget\b", r"\boperacao\b"],
                "Nao ha detalhamento suficiente de custo de uso, manutencao ou operacao.",
                "Adicionar estimativa de custo por ambiente, uso de modelos, RAG, logs e suporte.",
            ),
        ]

        findings: list[Finding] = []
        normalized = text.lower()
        for title, category, severity, patterns, explanation, recommendation in checks:
            if not any(re.search(pattern, normalized) for pattern in patterns):
                findings.append(
                    Finding(
                        title=title,
                        category=category,
                        severity=severity,  # type: ignore[arg-type]
                        finding_type="lacuna",
                        explanation=explanation,
                        recommendation=recommendation,
                        confidence="media",
                    )
                )
        return findings

    def _risk_keyword_findings(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for pattern, title, category, recommendation in [
            (
                r"(?i)\b(urgente|asap|imediat[oa])\b",
                "Prazo pode estar sendo tratado como premissa critica",
                "Cronograma",
                "Detalhar impacto do prazo em escopo, qualidade, testes e homologacao.",
            ),
            (
                r"(?i)\b(sem custo|custo zero|gratuito)\b",
                "Premissa de custo zero pode ser irrealista",
                "Custos",
                "Validar custos de modelo, RAG Engine, Cloud Run, logs e armazenamento.",
            ),
        ]:
            match = re.search(pattern, text)
            if match:
                evidence = _sentence_around(text, match.start())
                findings.append(
                    Finding(
                        title=title,
                        category=category,
                        severity="media",
                        finding_type="risco",
                        evidence=evidence,
                        explanation=(
                            "O trecho sugere uma premissa que precisa ser confirmada antes da "
                            "aprovacao tecnica."
                        ),
                        recommendation=recommendation,
                        confidence="baixa",
                    )
                )
        return findings

    def _build_summary(self, findings: list[Finding]) -> str:
        critical = sum(1 for finding in findings if finding.severity == "critica")
        high = sum(1 for finding in findings if finding.severity == "alta")
        gaps = sum(1 for finding in findings if finding.finding_type == "lacuna")
        return (
            f"Foram identificados {len(findings)} pontos de atencao: "
            f"{critical} criticos, {high} altos e {gaps} lacunas. "
            "Priorize lacunas de dados, privacidade, objetivo e criterios de aceite."
        )


def _sentence_around(text: str, index: int, radius: int = 180) -> str:
    start = max(0, index - radius)
    end = min(len(text), index + radius)
    excerpt = text[start:end].strip()
    return re.sub(r"\s+", " ", excerpt)
