"""Testes de integração — Agente 2 Finalizador (checklist completo)."""
import os
import sys
import tempfile

# Isolamento: redirecionar DB para arquivo temporário ANTES de importar main_fase2.
# DB_URL é lido via os.getenv("DATABASE_URL", ...) na linha 34 de main_fase2.py.
# O banco real jod_robo.db não é tocado.
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test_jod_robo.db"
os.environ.setdefault("JOD_ROBO_API_TOKEN", "dev-token")

sys.path.insert(0, "/home/wsl/JOD_ROBO")

import pytest
from fastapi.testclient import TestClient
from main_fase2 import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-token"}
_state: dict = {}


def setup_module(module):
    r = client.post("/agents/finalizer", json={"name": "test-fin-checklist"}, headers=AUTH)
    assert r.status_code == 200
    _state["agent_id"] = r.json()["agent_id"]


# 1. POST /agents/finalizer → agent_id presente, status draft
def test_create_returns_agent_id():
    assert "agent_id" in _state
    assert _state["agent_id"]


# 1b. auth obrigatório no create → 401 sem token
def test_create_requires_auth():
    r = client.post("/agents/finalizer", json={"name": "no-auth"})
    assert r.status_code == 401


# 2. GET manifest → público, retorna manifesto correto
def test_get_manifest_public():
    agent_id = _state["agent_id"]
    r = client.get(f"/agents/{agent_id}/finalizer/manifest")
    assert r.status_code == 200
    data = r.json()
    assert "allowed_actions" in data
    assert data["agent_id"] == agent_id


# 3. POST validate → draft → validated
def test_validate_agent():
    agent_id = _state["agent_id"]
    r = client.post(f"/agents/{agent_id}/finalizer/validate", headers=AUTH)
    assert r.status_code == 200


# 3b. auth obrigatório no validate → 401 sem token
def test_validate_requires_auth():
    agent_id = _state["agent_id"]
    r = client.post(f"/agents/{agent_id}/finalizer/validate")
    assert r.status_code == 401


# 4. POST activate → validated → active
def test_activate_agent():
    agent_id = _state["agent_id"]
    r = client.post(f"/agents/{agent_id}/finalizer/activate", headers=AUTH)
    assert r.status_code == 200


# 5. POST activate sem manifesto → 422
def test_activate_without_manifest():
    from main_fase2 import AgentRecord, AgentStatus, Session
    import uuid
    aid = str(uuid.uuid4())
    with Session() as s:
        s.add(AgentRecord(
            id=aid,
            name="sem-manifesto",
            role="tester",
            system_prompt="teste",
            status=AgentStatus.validated,
        ))
        s.commit()
    r = client.post(f"/agents/{aid}/finalizer/activate", headers=AUTH)
    assert r.status_code == 422


# 6. POST execute mode=plan → status planned, applied False
def test_execute_plan():
    agent_id = _state["agent_id"]
    r = client.post(
        f"/agents/{agent_id}/finalizer/execute",
        json={"mode": "plan", "action": "read_file", "target_path": "templates/finalizer_agent.json"},
        headers=AUTH,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "planned"
    assert data["applied"] is False


# 7. POST execute action=modify_manifest → forbidden
def test_execute_forbidden_action():
    agent_id = _state["agent_id"]
    r = client.post(
        f"/agents/{agent_id}/finalizer/execute",
        json={"mode": "dry_run", "action": "modify_manifest"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "forbidden"


# 8. POST execute action=git_push → needs_approval
def test_execute_needs_approval():
    agent_id = _state["agent_id"]
    r = client.post(
        f"/agents/{agent_id}/finalizer/execute",
        json={"mode": "dry_run", "action": "git_push"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "needs_approval"


# 9. POST execute path traversal → forbidden
def test_execute_path_traversal():
    agent_id = _state["agent_id"]
    r = client.post(
        f"/agents/{agent_id}/finalizer/execute",
        json={"mode": "dry_run", "action": "read_file", "target_path": "../../../etc/passwd"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "forbidden"


# 10. POST execute mode=dry_run action=read_file → dry_run_ok, applied False
def test_execute_dry_run_read_file():
    agent_id = _state["agent_id"]
    r = client.post(
        f"/agents/{agent_id}/finalizer/execute",
        json={"mode": "dry_run", "action": "read_file", "target_path": "templates/finalizer_agent.json"},
        headers=AUTH,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "dry_run_ok"
    assert data["applied"] is False


# 11. POST execute mode=apply action=write_file → status applied, snapshot_id preenchido
def test_execute_apply_write_file():
    agent_id = _state["agent_id"]
    r = client.post(
        f"/agents/{agent_id}/finalizer/execute",
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": "tests/_test_tmp_write.txt",
            "payload": "conteudo de teste",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "applied"
    assert data["applied"] is True
    assert data["snapshot_id"] is not None
    _state["snapshot_id"] = data["snapshot_id"]


# 12. POST rollback/{snap_id} → rolled_back True
def test_rollback():
    snap_id = _state.get("snapshot_id")
    assert snap_id is not None
    agent_id = _state["agent_id"]
    r = client.post(f"/agents/{agent_id}/finalizer/rollback/{snap_id}", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["rolled_back"] is True


# 13. GET audit → trilha com registros
def test_audit_trail():
    agent_id = _state["agent_id"]
    r = client.get(f"/agents/{agent_id}/finalizer/audit", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert "audit" in data
    assert len(data["audit"]) > 0


# 13b. auth obrigatório no audit → 401 sem token
def test_audit_requires_auth():
    agent_id = _state["agent_id"]
    r = client.get(f"/agents/{agent_id}/finalizer/audit")
    assert r.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
