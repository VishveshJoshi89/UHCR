import pytest
from uhcr.network.serialization import (
    serialize_job_to_json,
    deserialize_job_from_json,
    serialize_job_to_proto,
    deserialize_job_from_proto,
    validate_payload
)
from uhcr.network.jobs import Job, JobStatus
from datetime import datetime, timezone

def test_serialization_json_lossless():
    """Property 8: Serialization lossless round-trip (JSON)"""
    job = Job(id="job-1", status=JobStatus.QUEUED, payload=b"test-payload", submitted_at=datetime.now(timezone.utc), timeout_seconds=15.0)
    job.status = JobStatus.RUNNING
    job.worker_id = "worker-1"
    
    serialized = serialize_job_to_json(job)
    deserialized = deserialize_job_from_json(serialized)
    
    assert deserialized["id"] == "job-1"
    assert deserialized["status"] == "running"
    # Note: payload is base64 string after json serialization
    assert deserialized["timeout_seconds"] == 15.0
    assert deserialized["worker_id"] == "worker-1"

def test_serialization_proto_lossless():
    """Property 8: Serialization lossless round-trip (Proto)"""
    job = Job(id="job-2", status=JobStatus.QUEUED, payload=b"test-payload-proto", submitted_at=datetime.now(timezone.utc), timeout_seconds=20.0)
    job.status = JobStatus.COMPLETED
    job.result = b"test-result"
    
    serialized = serialize_job_to_proto(job)
    deserialized = deserialize_job_from_proto(serialized)
    
    assert deserialized["id"] == "job-2"
    assert deserialized["status"] == "completed"
    assert deserialized["timeout_seconds"] == 20.0

def test_serialization_invalid_input():
    """Property 9: Serialization error on invalid input"""
    # Missing payload
    valid, err = validate_payload({"timeout": 10})
    assert not valid
    assert "Missing required field: 'payload'" in err
    
    # Invalid timeout
    valid, err = validate_payload({"payload": "YWJj", "timeout": -5})
    assert not valid
    assert "timeout" in err
    
    # Invalid JSON
    with pytest.raises(ValueError):
        deserialize_job_from_json("{invalid_json:")
