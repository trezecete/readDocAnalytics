from typing import Literal

from pydantic import BaseModel, Field, model_validator

Severity = Literal["critica", "alta", "media", "baixa", "informativa"]
FindingType = Literal["risco", "inconsistencia", "lacuna", "recomendacao"]
Confidence = Literal["alta", "media", "baixa"]


class AnalysisCoverage(BaseModel):
    mode_label: str
    completeness_level: Literal["triagem", "rag_assistida", "completa_nao_garantida"]
    document_chars: int = Field(ge=0)
    document_bytes: int = Field(ge=0)
    text_scanned_percent: float = Field(ge=0, le=100)
    estimated_chunks: int = Field(ge=1)
    categories_checked: list[str]
    evidence_policy: str
    caveat: str


class Finding(BaseModel):
    title: str = Field(min_length=3)
    category: str = Field(min_length=3)
    severity: Severity
    finding_type: FindingType
    evidence: str | None = None
    explanation: str = Field(min_length=10)
    recommendation: str = Field(min_length=10)
    confidence: Confidence = "media"

    @model_validator(mode="after")
    def evidence_or_gap(self) -> "Finding":
        if self.finding_type in {"risco", "inconsistencia"} and not self.evidence:
            raise ValueError("risk and inconsistency findings require textual evidence")
        return self


class AnalysisReport(BaseModel):
    document_title: str
    executive_summary: str
    findings: list[Finding]
    recommendations: list[str]
    limitations: list[str]
    analyzer_backend: str
    coverage: AnalysisCoverage | None = None

    @property
    def critical_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "critica")

    @property
    def high_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "alta")
