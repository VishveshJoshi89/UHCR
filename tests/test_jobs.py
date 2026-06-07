import pytest
from datetime import datetime
import time

from uhcr.network.jobs import (
    JobManager,
    JobStatus,
    InvalidPayloadError,
    InvalidTransitionError
)

def test_job_submission():
    manager = JobManager(default_timeout=10.0)
    
    payload = b"UHCR_test_payload"
    job_id = manager.submit_job(payload=payload)
    
    assert job_id is not None
    job = manager.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.payload == payload
    assert job.timeout_seconds == 10.0

def test_job_submission_invalid_payload():
    manager = JobManager()
    with pytest.raises(InvalidPayloadError):
        manager.submit_job(payload=b"")  # Empty payload

def test_job_state_machine_valid_transitions():
    """Property 5: Job state machine valid transitions"""
    manager = JobManager()
    job_id = manager.submit_job(payload=b"valid")
    
    # queued -> running
    manager.start_job(job_id, worker_id="worker-1")
    assert manager.get_status(job_id) == JobStatus.RUNNING
    
    # running -> completed
    manager.complete_job(job_id, result=b"done")
    assert manager.get_status(job_id) == JobStatus.COMPLETED

def test_job_state_machine_invalid_transitions():
    manager = JobManager()
    job_id = manager.submit_job(payload=b"valid")
    
    # queued -> completed (invalid)
    with pytest.raises(InvalidTransitionError):
        manager.complete_job(job_id, result=b"done")

def test_job_monotonic_timestamps():
    """Property 6: Job monotonic timestamps"""
    manager = JobManager()
    job_id = manager.submit_job(payload=b"valid")
    job = manager.get_job(job_id)
    
    assert job.submitted_at is not None
    assert job.started_at is None
    assert job.completed_at is None
    
    time.sleep(0.01)
    manager.start_job(job_id, worker_id="w1")
    assert job.started_at is not None
    assert job.started_at >= job.submitted_at
    
    time.sleep(0.01)
    manager.complete_job(job_id, result=b"res")
    assert job.completed_at is not None
    assert job.completed_at >= job.started_at

def test_job_terminal_state_immutability():
    """Property 7: Job terminal state immutability"""
    manager = JobManager()
    job_id = manager.submit_job(payload=b"valid")
    
    manager.start_job(job_id, "w1")
    manager.complete_job(job_id, b"res")
    
    # Should not be able to fail a completed job
    with pytest.raises(InvalidTransitionError):
        manager.fail_job(job_id, "error")

def test_job_cancel():
    manager = JobManager()
    job_id = manager.submit_job(payload=b"valid")
    
    manager.cancel_job(job_id)
    assert manager.get_status(job_id) == JobStatus.TIMEOUT
    
    # Cancelling again does nothing
    manager.cancel_job(job_id)
    assert manager.get_status(job_id) == JobStatus.TIMEOUT

def test_list_jobs():
    manager = JobManager()
    id1 = manager.submit_job(payload=b"p1")
    id2 = manager.submit_job(payload=b"p2")
    
    manager.start_job(id1, "w1")
    manager.complete_job(id1, b"res")
    
    assert len(manager.list_jobs()) == 2
    assert len(manager.list_jobs(JobStatus.COMPLETED)) == 1
    assert len(manager.list_jobs(JobStatus.QUEUED)) == 1
