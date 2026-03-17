import pytest
import httpx

BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}


@pytest.fixture(scope="module")
def guardian_id():
    r = httpx.post(f"{BASE_URL}/agents/guardian",
                   json={"name": "test-guardian"},
                   headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "draft"
    assert "agent_id" in data
    return data["agent_id"]


def test_create_guardian(guardian_id):
    assert guardian_id is not None


def test_create_no_token():
    r = httpx.post(f"{BASE_URL}/agents/guardian", json={"name": "no-token"})
    assert r.status_code == 401


def test_validate_guardian(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/validate", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "validated"


def test_validate_no_token(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/validate")
    assert r.status_code == 401


def test_validate_already_validated(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/validate", headers=HEADERS)
    assert r.status_code == 409


def test_activate_guardian(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/activate", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_activate_no_token(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/activate")
    assert r.status_code == 401


def test_activate_already_active(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/activate", headers=HEADERS)
    assert r.status_code == 409


def test_check_blocked_action(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/check",
                   json={"action": "modify_manifest"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"


def test_check_needs_approval_action(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/check",
                   json={"action": "git_push"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "needs_approval"


def test_check_approved_action(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/check",
                   json={"action": "read_file"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_check_inactive_agent():
    r = httpx.post(f"{BASE_URL}/agents/guardian",
                   json={"name": "inactive-guardian"}, headers=HEADERS)
    assert r.status_code == 200
    inactive_id = r.json()["agent_id"]
    r2 = httpx.post(f"{BASE_URL}/agents/{inactive_id}/guardian/check",
                    json={"action": "read_file"}, headers=HEADERS)
    assert r2.status_code == 409


def test_check_no_token(guardian_id):
    r = httpx.post(f"{BASE_URL}/agents/{guardian_id}/guardian/check",
                   json={"action": "read_file"})
    assert r.status_code == 401


def test_audit_trail(guardian_id):
    r = httpx.get(f"{BASE_URL}/agents/{guardian_id}/guardian/audit", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "audit" in data
    assert len(data["audit"]) > 0


def test_audit_no_token(guardian_id):
    r = httpx.get(f"{BASE_URL}/agents/{guardian_id}/guardian/audit")
    assert r.status_code == 401
