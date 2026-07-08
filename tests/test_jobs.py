from app.jobs import JobStage, JobStatus, JobStore, estimate_total_seconds


def test_job_status_progress_snapshot():
    store = JobStore()
    job = store.create(
        session_id="session-1",
        document_url="https://docs.google.com/document/d/example/edit",
        credentials_payload={"token": "token", "scopes": ["scope"]},
    )

    assert job.snapshot()["status"] == JobStatus.QUEUED.value

    job.start()
    job.set_stage(JobStage.ORGANIZING)

    snapshot = job.snapshot()
    assert snapshot["status"] == JobStatus.RUNNING.value
    assert snapshot["stage"] == JobStage.ORGANIZING.value
    assert snapshot["progress"] >= 30


def test_estimate_total_seconds_scales_by_backend_and_size():
    small_local = estimate_total_seconds(20_000, "local")
    large_local = estimate_total_seconds(4_000_000, "local")
    small_ai = estimate_total_seconds(20_000, "gemini_rag")
    large_ai = estimate_total_seconds(4_000_000, "gemini_rag")

    assert small_local < small_ai
    assert small_local <= large_local <= 60
    assert small_ai <= large_ai <= 420
