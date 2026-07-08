from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock

from app.analysis.models import AnalysisReport
from app.docs_reader.models import DocumentContent


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStage(StrEnum):
    PREPARING = "preparing"
    READING = "reading"
    ORGANIZING = "organizing"
    PREPARING_CONTEXT = "preparing_context"
    RETRIEVING_EVIDENCE = "retrieving_evidence"
    GENERATING_REPORT = "generating_report"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


STAGE_LABELS: dict[JobStage, str] = {
    JobStage.PREPARING: "Preparando análise",
    JobStage.READING: "Acessando documento",
    JobStage.ORGANIZING: "Organizando conteúdo",
    JobStage.PREPARING_CONTEXT: "Preparando base de consulta",
    JobStage.RETRIEVING_EVIDENCE: "Consultando evidências",
    JobStage.GENERATING_REPORT: "Gerando relatório",
    JobStage.FINALIZING: "Finalizando arquivo",
    JobStage.COMPLETED: "Relatório pronto",
    JobStage.FAILED: "Não foi possível concluir",
}

STAGE_PROGRESS: dict[JobStage, int] = {
    JobStage.PREPARING: 5,
    JobStage.READING: 15,
    JobStage.ORGANIZING: 30,
    JobStage.PREPARING_CONTEXT: 48,
    JobStage.RETRIEVING_EVIDENCE: 68,
    JobStage.GENERATING_REPORT: 86,
    JobStage.FINALIZING: 96,
    JobStage.COMPLETED: 100,
    JobStage.FAILED: 100,
}


@dataclass
class AnalysisJob:
    job_id: str
    session_id: str
    document_url: str
    credentials_payload: dict
    status: JobStatus = JobStatus.QUEUED
    stage: JobStage = JobStage.PREPARING
    message: str = STAGE_LABELS[JobStage.PREPARING]
    progress: int = STAGE_PROGRESS[JobStage.PREPARING]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_total_seconds: int = 120
    document: DocumentContent | None = None
    report: AnalysisReport | None = None
    error: str | None = None
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def start(self) -> None:
        with self._lock:
            now = datetime.now(UTC)
            self.status = JobStatus.RUNNING
            self.started_at = now
            self.updated_at = now
            self.set_stage(JobStage.READING)

    def set_stage(self, stage: JobStage, message: str | None = None) -> None:
        now = datetime.now(UTC)
        self.stage = stage
        self.message = message or STAGE_LABELS[stage]
        self.progress = max(self.progress, STAGE_PROGRESS[stage])
        self.updated_at = now

    def set_document(self, document: DocumentContent, backend: str) -> None:
        with self._lock:
            self.document = document
            self.estimated_total_seconds = estimate_total_seconds(
                document.byte_count,
                backend,
            )
            self.updated_at = datetime.now(UTC)

    def complete(self, report: AnalysisReport) -> None:
        with self._lock:
            now = datetime.now(UTC)
            self.report = report
            self.status = JobStatus.COMPLETED
            self.stage = JobStage.COMPLETED
            self.message = STAGE_LABELS[JobStage.COMPLETED]
            self.progress = 100
            self.completed_at = now
            self.updated_at = now

    def fail(self, error: str) -> None:
        with self._lock:
            now = datetime.now(UTC)
            self.status = JobStatus.FAILED
            self.stage = JobStage.FAILED
            self.message = STAGE_LABELS[JobStage.FAILED]
            self.progress = 100
            self.error = error
            self.completed_at = now
            self.updated_at = now

    @property
    def elapsed_seconds(self) -> int:
        start = self.started_at or self.created_at
        end = self.completed_at or datetime.now(UTC)
        return max(0, int((end - start).total_seconds()))

    @property
    def remaining_seconds(self) -> int:
        if self.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return 0
        return max(0, self.estimated_total_seconds - self.elapsed_seconds)

    def snapshot(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "stage": self.stage.value,
            "stage_label": STAGE_LABELS[self.stage],
            "message": self.message,
            "progress": self.progress,
            "elapsed_seconds": self.elapsed_seconds,
            "remaining_seconds": self.remaining_seconds,
            "estimated_total_seconds": self.estimated_total_seconds,
            "error": self.error,
            "result_url": f"/analysis/jobs/{self.job_id}"
            if self.status == JobStatus.COMPLETED
            else None,
        }


def estimate_total_seconds(document_bytes: int | None, backend: str) -> int:
    if not document_bytes:
        return 90 if backend == "local" else 180

    size_mb = document_bytes / 1_000_000
    if backend == "local":
        return max(12, min(60, int(8 + size_mb * 8)))

    return max(90, min(420, int(95 + size_mb * 55)))
