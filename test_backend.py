"""
Unit and Integration Tests for GridGuard FastAPI Backend
Tests:
1. Lifespan startup and model loading
2. Class name mapping & severity logic
3. REST endpoints: GET /, GET /events, GET /status, POST /simulate
4. WebSocket broadcasting at /ws and JSON shape verification
5. In-memory event log cap (100 events)
"""

import json
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend import app, CLASS_NAMES, determine_severity_and_relay, event_log

client = TestClient(app)

def test_class_names_order():
    """Verify exact 8 IEEE 1159 classes in the specified order."""
    expected = [
        "Normal",
        "Voltage Sag",
        "Voltage Swell",
        "Interruption",
        "Flicker",
        "Transient Spike",
        "Harmonic Distortion",
        "Notching"
    ]
    assert CLASS_NAMES == expected, f"Class names mismatch: {CLASS_NAMES} vs {expected}"

def test_severity_and_relay_logic():
    """Verify exact severity and relay action rules."""
    # Normal -> severity: "normal", relay_action: "HOLD"
    sev, act = determine_severity_and_relay("Normal")
    assert sev == "normal" and act == "HOLD"

    # Warning -> TRIP
    for cls in ["Voltage Sag", "Voltage Swell", "Flicker"]:
        sev, act = determine_severity_and_relay(cls)
        assert sev == "warning", f"Expected warning for {cls}, got {sev}"
        assert act == "TRIP", f"Expected TRIP for {cls}, got {act}"

    # Critical -> TRIP
    for cls in ["Transient Spike", "Harmonic Distortion", "Interruption", "Notching"]:
        sev, act = determine_severity_and_relay(cls)
        assert sev == "critical", f"Expected critical for {cls}, got {sev}"
        assert act == "TRIP", f"Expected TRIP for {cls}, got {act}"

def test_root_endpoint():
    """Verify GET / returns project health and status."""
    with TestClient(app) as tc:
        resp = tc.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project"] == "GridGuard"
        assert data["model_loaded"] is True

def test_events_endpoint():
    """Verify GET /events returns in-memory events."""
    with TestClient(app) as tc:
        resp = tc.get("/events")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

def test_status_endpoint():
    """Verify GET /status diagnostics."""
    with TestClient(app) as tc:
        resp = tc.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "model" in data
        assert "mqtt" in data
        assert "websockets" in data

def test_simulate_and_websocket_broadcast():
    """
    Simulate feature vector, verify exact JSON shape on WebSocket:
    {
      "line": "A",
      "classification": "Voltage Sag",
      "features": { "rms": 0.57, "crest_factor": 1.83, "thd": 0.06, "band_energy": 0.008 },
      "severity": "warning",
      "relay_action": "TRIP",
      "timestamp": "2026-10-13T19:03:00"
    }
    """
    with TestClient(app) as tc:
        with tc.websocket_connect("/ws") as ws:
            # Send simulation request via REST
            req_payload = {
                "line": "A",
                "features": [0.57, 1.83, 0.06, 0.008]
            }
            resp = tc.post("/simulate", json=req_payload)
            assert resp.status_code == 200
            rest_data = resp.json()

            # Read broadcast from WebSocket
            ws_msg = ws.receive_json()

            # Check JSON shape matches REST response and spec
            assert ws_msg["line"] == "A"
            assert "classification" in ws_msg
            assert ws_msg["classification"] in CLASS_NAMES
            assert "features" in ws_msg
            assert ws_msg["features"]["rms"] == 0.57
            assert ws_msg["features"]["crest_factor"] == 1.83
            assert ws_msg["features"]["thd"] == 0.06
            assert ws_msg["features"]["band_energy"] == 0.008
            assert ws_msg["severity"] in ("normal", "warning", "critical")
            assert ws_msg["relay_action"] in ("HOLD", "TRIP")
            
            # Timestamp check (ISO-like string YYYY-MM-DDTHH:MM:SS)
            datetime.fromisoformat(ws_msg["timestamp"])

def test_event_log_max_limit():
    """Verify in-memory event log does not exceed 100 entries."""
    with TestClient(app) as tc:
        event_log.clear()
        for i in range(120):
            tc.post("/simulate", json={"line": "B", "features": [1.0, 1.41, 0.01, 0.001]})
        
        resp = tc.get("/events")
        data = resp.json()
        assert len(data) == 100, f"Expected 100 events, got {len(data)}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
