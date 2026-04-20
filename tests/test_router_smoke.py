"""
Smoke tests — one per router — so CI turns green on every touched file.

Each test hits the lightest happy-path endpoint that doesn't touch the TTS
model or hit network. The point is not coverage depth — we have richer tests
for that elsewhere — but to catch "the module doesn't import" / "the route is
gone" regressions on every PR.
"""
import os
import pytest

os.environ.setdefault("OMNIVOICE_MODEL", "test")
os.environ.setdefault("OMNIVOICE_DISABLE_FILE_LOG", "1")


@pytest.fixture(scope="module")
def client():
    # Lazy import so test_api.py's session fixtures can mock the model first
    # if both suites run together.
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


# ── system ──────────────────────────────────────────────────────────────────
def test_system_info_smoke(client):
    r = client.get("/system/info")
    assert r.status_code == 200
    body = r.json()
    assert "data_dir" in body
    assert "device" in body


def test_system_logs_smoke(client):
    r = client.get("/system/logs?tail=10")
    assert r.status_code == 200
    assert "lines" in r.json()


def test_system_logs_tauri_smoke(client):
    r = client.get("/system/logs/tauri?tail=10")
    # 200 whether file exists or not — the endpoint just reports either way.
    assert r.status_code == 200
    body = r.json()
    assert "exists" in body


def test_model_status_smoke(client):
    r = client.get("/model/status")
    assert r.status_code == 200
    assert "status" in r.json()


def test_sysinfo_smoke(client):
    r = client.get("/sysinfo")
    assert r.status_code == 200
    assert "cpu" in r.json()


# ── profiles ────────────────────────────────────────────────────────────────
def test_profiles_list_smoke(client):
    r = client.get("/profiles")
    # Empty list is fine on a fresh DB; the point is that the module imports
    # and the route exists.
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── projects ────────────────────────────────────────────────────────────────
def test_projects_list_smoke(client):
    r = client.get("/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── exports ─────────────────────────────────────────────────────────────────
def test_export_history_smoke(client):
    r = client.get("/export/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_export_reveal_rejects_empty_path(client):
    # Validates the rewritten error message reaches the client cleanly.
    r = client.post("/export/reveal", json={"path": ""})
    assert r.status_code == 400
    assert "nothing to reveal" in r.json()["detail"].lower()


# ── generation ──────────────────────────────────────────────────────────────
def test_history_list_smoke(client):
    r = client.get("/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── dub_core ────────────────────────────────────────────────────────────────
def test_dub_history_list_smoke(client):
    r = client.get("/dub/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_dub_generate_unknown_job(client):
    # Hitting /dub/generate/{id} with a non-existent id should surface the
    # rewritten 404 copy.
    r = client.post("/dub/generate/__nonexistent__", json={
        "segments": [],
        "language": "Auto",
        "language_code": "und",
        "num_step": 16,
        "guidance_scale": 2.0,
        "speed": 1.0,
    })
    assert r.status_code == 404
    assert "re-upload" in r.json()["detail"].lower()
