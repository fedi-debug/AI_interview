import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_interview_requires_consent(client):
    r = await client.post("/interview/start", json={"job_title": "SE", "consent": False})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_interview_start(client):
    r = await client.post("/interview/start", json={"job_title": "SE", "consent": True})
    assert r.status_code == 200
    assert "session_id" in r.json()
