import pytest
import asyncio
from uhcr.network.grpc_service import UHCRServicer, _JobResponse, _JobStatusResponse
from uhcr.network.jobs import JobManager, JobStatus

@pytest.mark.asyncio
async def test_grpc_submit_job():
    manager = JobManager()
    servicer = UHCRServicer(manager)
    
    # Mock request
    request = {"payload": b"hello", "timeout_seconds": 10.0}
    response = await servicer.SubmitJob(request, None)
    
    assert response.job_id != ""
    assert response.status == JobStatus.QUEUED.value

@pytest.mark.asyncio
async def test_grpc_get_job_status():
    manager = JobManager()
    servicer = UHCRServicer(manager)
    
    job_id = manager.submit_job(b"hello")
    request = {"job_id": job_id}
    
    response = await servicer.GetJobStatus(request, None)
    
    assert response.job_id == job_id
    assert response.status == JobStatus.QUEUED.value
    assert response.error == ""

@pytest.mark.asyncio
async def test_grpc_get_job_status_not_found():
    manager = JobManager()
    servicer = UHCRServicer(manager)
    
    request = {"job_id": "invalid"}
    response = await servicer.GetJobStatus(request, None)
    
    assert response.job_id == "invalid"
    assert "Job not found" in response.error

@pytest.mark.asyncio
async def test_grpc_stream_results_not_completed():
    manager = JobManager()
    servicer = UHCRServicer(manager)
    
    job_id = manager.submit_job(b"hello")
    request = {"job_id": job_id}
    
    chunks = []
    async for chunk in servicer.StreamResults(request, None):
        chunks.append(chunk)
        
    assert len(chunks) == 0  # Not completed, returns nothing (or aborts if context provided)

@pytest.mark.asyncio
async def test_grpc_stream_results_completed():
    manager = JobManager()
    servicer = UHCRServicer(manager)
    
    job_id = manager.submit_job(b"hello")
    manager.start_job(job_id, "w1")
    manager.complete_job(job_id, b"result_data")
    
    request = {"job_id": job_id}
    
    chunks = []
    async for chunk in servicer.StreamResults(request, None):
        chunks.append(chunk)
        
    assert len(chunks) == 1
    assert chunks[0].data == b"result_data"
    assert chunks[0].is_last
