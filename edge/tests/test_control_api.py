"""
Tests for the battery control HTTP API (FastAPI app).

Verifies bearer-token auth, the force/auto/status/audit endpoints, and that
validation failures surface as HTTP 422 without touching Modbus.

CHANGELOG:
- 2026-07-18: Initial creation -- TDD tests written first (battery-control AC6)

TODO:
- None
"""

from __future__ import annotations

import httpx
import pytest
from edge.src.control import ControlLimits, SungrowController
from edge.src.control_api import build_app

from .test_control import FakeClock, FakeModbusClient

TOKEN = "test-token-123"


def make_app(tmp_path, fake_client, clock, *, dry_run=True):
    ctrl = SungrowController(
        host="192.0.2.1",
        port=502,
        slave_id=1,
        limits=ControlLimits(),
        dry_run=dry_run,
        state_path=str(tmp_path / "state.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        client_factory=lambda: fake_client,
        now_fn=clock,
    )
    ctrl.observe_soc(50.0)
    return build_app(ctrl, token=TOKEN), ctrl


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.asyncio
async def test_missing_token_rejected(tmp_path):
    app, _ = make_app(tmp_path, FakeModbusClient(), FakeClock())
    async with client_for(app) as c:
        resp = await c.get("/control/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_token_rejected(tmp_path):
    app, _ = make_app(tmp_path, FakeModbusClient(), FakeClock())
    async with client_for(app) as c:
        resp = await c.get(
            "/control/status", headers={"Authorization": "Bearer nope"}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_shape(tmp_path):
    app, _ = make_app(tmp_path, FakeModbusClient(), FakeClock())
    async with client_for(app) as c:
        resp = await c.get("/control/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["active"] is None
    assert body["limits"]["max_charge_w"] == 4000
    assert body["last_soc_pct"] == 50.0


@pytest.mark.asyncio
async def test_force_dry_run_accepted(tmp_path):
    fake = FakeModbusClient()
    app, _ = make_app(tmp_path, fake, FakeClock())
    async with client_for(app) as c:
        resp = await c.post(
            "/control/force",
            headers=AUTH,
            json={"mode": "charge", "power_w": 2000, "ttl_s": 900, "issuer": "pytest"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["dry_run"] is True
    assert fake.writes == []


@pytest.mark.asyncio
async def test_force_validation_error_is_422(tmp_path):
    app, _ = make_app(tmp_path, FakeModbusClient(), FakeClock())
    async with client_for(app) as c:
        resp = await c.post(
            "/control/force",
            headers=AUTH,
            json={"mode": "charge", "power_w": 0, "ttl_s": 900, "issuer": "pytest"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_auto_endpoint_clears_active(tmp_path):
    fake = FakeModbusClient()
    clock = FakeClock()
    app, ctrl = make_app(tmp_path, fake, clock)
    async with client_for(app) as c:
        await c.post(
            "/control/force",
            headers=AUTH,
            json={"mode": "hold", "ttl_s": 900, "issuer": "pytest"},
        )
        assert ctrl.status()["active"] is not None
        resp = await c.post(
            "/control/auto", headers=AUTH, json={"issuer": "pytest"}
        )
    assert resp.status_code == 200
    assert ctrl.status()["active"] is None


@pytest.mark.asyncio
async def test_audit_endpoint_returns_events(tmp_path):
    app, _ = make_app(tmp_path, FakeModbusClient(), FakeClock())
    async with client_for(app) as c:
        await c.post(
            "/control/force",
            headers=AUTH,
            json={"mode": "hold", "ttl_s": 900, "issuer": "pytest"},
        )
        resp = await c.get("/control/audit", headers=AUTH, params={"limit": 10})
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert any(e["event"] == "command_accepted" for e in events)


@pytest.mark.asyncio
async def test_root_serves_ui_without_token(tmp_path):
    """GET / is the operator page: public static shell, HTML, no auth."""
    app, _ = make_app(tmp_path, FakeModbusClient(), FakeClock())
    async with client_for(app) as c:
        resp = await c.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Battery control" in resp.text


@pytest.mark.asyncio
async def test_root_page_contains_no_secrets(tmp_path):
    """The unauthenticated shell must never embed the API token."""
    app, _ = make_app(tmp_path, FakeModbusClient(), FakeClock())
    async with client_for(app) as c:
        resp = await c.get("/")
    assert TOKEN not in resp.text
