import pytest
from aiohttp import web
import json
from uhcr.network.health import HealthService, setup_health_routes

class MockJobManager:
    def list_jobs(self, status):
        if status.value == "queued":
            return [1, 2]
        elif status.value == "running":
            return [3]
        return []
    
    def job_count(self):
        return 3

class MockServer:
    uptime = 1000.5
    workers = ["w1", "w2"]

@pytest.fixture
def health_service():
    return HealthService(MockJobManager(), MockServer(), overload_threshold=5)

@pytest.mark.asyncio
async def test_health_live(health_service):
    app = web.Application()
    setup_health_routes(app, health_service)
    
    # Create mock request
    req = type('Request', (), {'app': app})()
    
    response = await health_service.handle_liveness(req)
    assert response.status == 200
    body = json.loads(response.body.decode('utf-8'))
    assert body["status"] == "alive"

@pytest.mark.asyncio
async def test_health_ready_ok(health_service):
    app = web.Application()
    req = type('Request', (), {'app': app})()
    
    response = await health_service.handle_readiness(req)
    assert response.status == 200
    body = json.loads(response.body.decode('utf-8'))
    assert body["status"] == "ready"
    assert body["active_jobs"] == 3
    assert body["connected_workers"] == 2
    assert body["uptime_seconds"] == 1000.5

@pytest.mark.asyncio
async def test_health_ready_overloaded(health_service):
    # Set threshold low to force overload
    health_service._overload_threshold = 2
    
    app = web.Application()
    req = type('Request', (), {'app': app})()
    
    response = await health_service.handle_readiness(req)
    assert response.status == 503
    body = json.loads(response.body.decode('utf-8'))
    assert body["status"] == "overloaded"
