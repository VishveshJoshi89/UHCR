import pytest
import time
from datetime import datetime, timezone, timedelta
from uhcr.network.coordinator import CoordinatorNode, WorkerInfo

def test_coordinator_worker_registration():
    coord = CoordinatorNode()
    worker = WorkerInfo(
        id="w1", address="127.0.0.1:8000", architecture="x86_64", 
        simd_capabilities=["avx2"], available_memory_mb=1024,
        last_heartbeat=datetime.now(timezone.utc)
    )
    w_id = coord.register_worker(worker)
    assert w_id == "w1"
    
    assert len(coord.list_workers()) == 1
    
    coord.deregister_worker("w1")
    assert len(coord.list_workers()) == 0

def test_distributed_coordination_no_orphaned_jobs():
    """Property 10: Distributed coordination no orphaned jobs"""
    coord = CoordinatorNode()
    w1 = WorkerInfo(
        id="w1", address="127.0.0.1:8000", architecture="x86_64", 
        simd_capabilities=[], available_memory_mb=1024,
        last_heartbeat=datetime.now(timezone.utc)
    )
    w2 = WorkerInfo(
        id="w2", address="127.0.0.1:8001", architecture="aarch64", 
        simd_capabilities=[], available_memory_mb=1024,
        last_heartbeat=datetime.now(timezone.utc)
    )
    coord.register_worker(w1)
    coord.register_worker(w2)
    
    # Assign job, w1 should get it first (round robin or least loaded)
    assigned_id = coord.assign_job("job-1", strategy="least-loaded")
    assert assigned_id is not None
    worker = coord.get_worker(assigned_id)
    assert worker.active_jobs == 1
    
    assigned_id2 = coord.assign_job("job-2", strategy="least-loaded")
    worker2 = coord.get_worker(assigned_id2)
    assert worker2.active_jobs == 1
    assert assigned_id != assigned_id2

def test_distributed_coordination_heartbeat_liveness():
    """Property 11: Distributed coordination heartbeat liveness"""
    coord = CoordinatorNode()
    
    past_time = datetime.now(timezone.utc) - timedelta(seconds=40)
    w1 = WorkerInfo(
        id="w1", address="127.0.0.1:8000", architecture="x86_64", 
        simd_capabilities=[], available_memory_mb=1024,
        last_heartbeat=past_time
    )
    coord.register_worker(w1)
    
    unhealthy = coord.check_worker_health(threshold_seconds=30.0)
    assert "w1" in unhealthy
    
    w1_info = coord.get_worker("w1")
    assert not w1_info.healthy
    
    coord.update_heartbeat("w1")
    w1_info = coord.get_worker("w1")
    assert w1_info.healthy

def test_hardware_affinity_scheduling():
    coord = CoordinatorNode()
    w1 = WorkerInfo(
        id="w1", address="127.0.0.1:8000", architecture="x86_64", 
        simd_capabilities=[], available_memory_mb=1024,
        last_heartbeat=datetime.now(timezone.utc)
    )
    w2 = WorkerInfo(
        id="w2", address="127.0.0.1:8001", architecture="aarch64", 
        simd_capabilities=["neon"], available_memory_mb=1024,
        last_heartbeat=datetime.now(timezone.utc)
    )
    coord.register_worker(w1)
    coord.register_worker(w2)
    
    # Needs aarch64
    assigned = coord.assign_job("job_arch:aarch64", strategy="hardware-affinity")
    assert assigned == "w2"
    
    # Needs x86_64
    assigned2 = coord.assign_job("job_arch:x86_64", strategy="hardware-affinity")
    assert assigned2 == "w1"
