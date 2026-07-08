from __future__ import annotations

from threading import Lock
from uuid import uuid4

from app.jobs.models import AnalysisJob


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = Lock()

    def create(
        self,
        *,
        session_id: str,
        document_url: str,
        credentials_payload: dict,
    ) -> AnalysisJob:
        job = AnalysisJob(
            job_id=uuid4().hex,
            session_id=session_id,
            document_url=document_url,
            credentials_payload=credentials_payload,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> AnalysisJob | None:
        with self._lock:
            return self._jobs.get(job_id)

