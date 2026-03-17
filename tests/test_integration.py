import json as _json
import pytest
import httpx
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
BASE_DIR = Path("/home/wsl/JOD_ROBO")
DB_PATH  = BASE_DIR / "jod_robo.db"

_engine_test = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
_SessionTest = sessionmaker(bind=_engine_test, autoflush=False, autocommit=False)

# Manifest válido explícito — espelho de _DEFAULT_FINALIZER_MANIFEST
_VALID_MANIFEST = {
    "allowed_actions":   ["write_file", "read_file", "list_dir"],
    "allowed_paths":     ["agents/", "scripts/", "templates/", "tests/"],
    "forbidden_paths":   [
        "app/", "jod_brain/", ".env", "main_fase2.py",
        "jod_brain_main.py", "requirements.txt", "Dockerfile",
        "templates/finalizer_manifest.json",
    ],
    "allowed_hosts":     [],
    "requires_approval": ["run_script", "git_push", "delete_file", "access_secret", "edit_core"],
}


# ---------------------------------------------------------------------------
# Fixture: cria + ativa Finalizador (com manifest válido explícito) e Guardião
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def agents():
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        json={"name": "test-int-finalizer", "manifest": _VALID_MANIFEST},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    fin_id = r.json()["agent_id"]
    httpx.post(f"{BASE_URL}/agents/{fin_id}/finalizer/validate", headers=HEADERS)
    httpx.post(f"{BASE_URL}/agents/{fin_id}/finalizer/activate", headers=HEADERS)

    r = httpx.post(f"{BASE_URL}/agents/guardian",
                   json={"name": "test-int-guardian"}, headers=HEADERS)
    assert r.status_code == 200, r.text
    grd_id = r.json()["agent_id"]
    httpx.post(f"{BASE_URL}/agents/{grd_id}/guardian/validate", headers=HEADERS)
    httpx.post(f"{BASE_URL}/agents/{grd_id}/guardian/activate", headers=HEADERS)

    return {"finalizer_id": fin_id, "guardian_id": grd_id}


# ---------------------------------------------------------------------------
# Fixture: executa write_file com guardian e captura resultado completo
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def e2e_write(agents):
    r = httpx.post(
        f"{BASE_URL}/agents/{agents['finalizer_id']}/finalizer/execute",
        json={
            "mode":        "apply",
            "action":      "write_file",
            "target_path": "agents/test_int_e2e.txt",
            "payload":     "integration baseline e2e",
            "guardian_id": agents["guardian_id"],
        },
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Rastreabilidade end-to-end — caminho aprovado
# ---------------------------------------------------------------------------
def test_e2e_status_applied(e2e_write):
    assert e2e_write["status"]  == "applied"
    assert e2e_write["applied"] is True


def test_e2e_evidence_has_guardian_transaction_id(e2e_write):
    """Response.evidence contém guardian_transaction_id não nulo."""
    assert e2e_write.get("evidence") is not None
    assert "guardian_transaction_id" in e2e_write["evidence"]
    assert e2e_write["evidence"]["guardian_transaction_id"] is not None


def test_e2e_finalizer_audit_carries_guardian_transaction_id(agents, e2e_write):
    """finalizer_audit.details.evidence.guardian_transaction_id == transaction_id do response."""
    gtxid = e2e_write["evidence"]["guardian_transaction_id"]

    r = httpx.get(
        f"{BASE_URL}/agents/{agents['finalizer_id']}/finalizer/audit",
        headers=HEADERS,
    )
    assert r.status_code == 200
    entries = r.json()["audit"]

    matched = [
        e for e in entries
        if isinstance(e.get("details"), dict)
        and e["details"].get("evidence", {}).get("guardian_transaction_id") == gtxid
    ]
    assert len(matched) >= 1, (
        f"Nenhuma entrada em finalizer_audit com guardian_transaction_id={gtxid}. "
        f"Details das 3 primeiras: {[e.get('details') for e in entries[:3]]}"
    )


def test_e2e_integration_audit_record(agents, e2e_write):
    """integration_audit: registro correto via row._mapping."""
    gtxid = e2e_write["evidence"]["guardian_transaction_id"]

    with _SessionTest() as s:
        rows = list(s.execute(
            text(
                "SELECT finalizer_id, guardian_id, action, guardian_status, transaction_id "
                "FROM integration_audit WHERE transaction_id = :txid"
            ),
            {"txid": gtxid},
        ))

    assert len(rows) == 1, f"Esperado 1 registro, encontrado {len(rows)}"
    m = rows[0]._mapping
    assert m["finalizer_id"]    == agents["finalizer_id"]
    assert m["guardian_id"]     == agents["guardian_id"]
    assert m["action"]          == "write_file"
    assert m["guardian_status"] == "approved"
    assert m["transaction_id"]  == gtxid


def test_e2e_guardian_audit_cross_trail(agents, e2e_write):
    """guardian_audit: trilha cruzada com mesmo transaction_id.
    Candidatos carregados por agent_id+status; filtro por transaction_id em Python."""
    gtxid = e2e_write["evidence"]["guardian_transaction_id"]

    with _SessionTest() as s:
        candidate_rows = list(s.execute(
            text(
                "SELECT agent_id, action, status, details "
                "FROM guardian_audit "
                "WHERE agent_id = :gid AND status LIKE 'attested:%' "
                "ORDER BY rowid DESC LIMIT 50"
            ),
            {"gid": agents["guardian_id"]},
        ))

    matched = [
        r for r in candidate_rows
        if _json.loads(r._mapping["details"]).get("transaction_id") == gtxid
    ]
    assert len(matched) >= 1, (
        f"Nenhuma trilha cruzada em guardian_audit para transaction_id={gtxid}"
    )
    m = matched[0]._mapping
    assert m["agent_id"] == agents["guardian_id"]
    assert m["status"].startswith("attested:")

    details = _json.loads(m["details"])
    assert details["transaction_id"] == gtxid
    assert details["finalizer_id"]   == agents["finalizer_id"]
    assert "integration_audit_id"    in details


# ---------------------------------------------------------------------------
# 2. Caminhos de erro do gate: 404 e 409
# ---------------------------------------------------------------------------
def test_guardian_not_found_returns_404(agents):
    """guardian inexistente → 404; arquivo não escrito no disco."""
    target = "agents/test_int_404.txt"
    r = httpx.post(
        f"{BASE_URL}/agents/{agents['finalizer_id']}/finalizer/execute",
        json={
            "mode":        "apply",
            "action":      "write_file",
            "target_path": target,
            "payload":     "nao deve ser escrito",
            "guardian_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=HEADERS,
    )
    assert r.status_code == 404
    assert not (BASE_DIR / target).exists()


def test_guardian_not_active_returns_409(agents):
    """guardian não ativo → 409; arquivo não escrito no disco."""
    r = httpx.post(f"{BASE_URL}/agents/guardian",
                   json={"name": "inactive-int-guardian"}, headers=HEADERS)
    assert r.status_code == 200
    inactive_id = r.json()["agent_id"]

    target = "agents/test_int_409.txt"
    r2 = httpx.post(
        f"{BASE_URL}/agents/{agents['finalizer_id']}/finalizer/execute",
        json={
            "mode":        "apply",
            "action":      "write_file",
            "target_path": target,
            "payload":     "nao deve ser escrito",
            "guardian_id": inactive_id,
        },
        headers=HEADERS,
    )
    assert r2.status_code == 409
    assert not (BASE_DIR / target).exists()


# ---------------------------------------------------------------------------
# 3. Escrita sem guardian_id — mudança explícita: shadow + os.replace universal
# ---------------------------------------------------------------------------
def test_write_without_guardian_applies_via_shadow(agents):
    """write_file sem guardian_id → applied via shadow+os.replace, sem gate."""
    r = httpx.post(
        f"{BASE_URL}/agents/{agents['finalizer_id']}/finalizer/execute",
        json={
            "mode":        "apply",
            "action":      "write_file",
            "target_path": "agents/test_int_no_guardian.txt",
            "payload":     "sem guardian",
        },
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"]  == "applied"
    assert data["applied"] is True
    assert "guardian_transaction_id" not in (data.get("evidence") or {})


# ---------------------------------------------------------------------------
# 4. dry_run com guardian_id não aciona o gate
# ---------------------------------------------------------------------------
def test_dry_run_does_not_trigger_gate(agents):
    """dry_run com guardian_id → dry_run_ok; integration_audit sem novo registro."""
    with _SessionTest() as s:
        count_before = list(s.execute(
            text("SELECT COUNT(*) FROM integration_audit WHERE finalizer_id = :fid"),
            {"fid": agents["finalizer_id"]},
        ))[0][0]

    r = httpx.post(
        f"{BASE_URL}/agents/{agents['finalizer_id']}/finalizer/execute",
        json={
            "mode":        "dry_run",
            "action":      "write_file",
            "target_path": "agents/test_int_dryrun.txt",
            "payload":     "dry",
            "guardian_id": agents["guardian_id"],
        },
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"]  == "dry_run_ok"
    assert r.json()["applied"] is False

    with _SessionTest() as s:
        count_after = list(s.execute(
            text("SELECT COUNT(*) FROM integration_audit WHERE finalizer_id = :fid"),
            {"fid": agents["finalizer_id"]},
        ))[0][0]

    assert count_after == count_before


# ---------------------------------------------------------------------------
# 5. Ausência de shadow files órfãos
# ---------------------------------------------------------------------------
def test_no_orphan_shadow_files():
    """Nenhum .*.jod_tmp no disco após escritas bem-sucedidas."""
    orphans = list(BASE_DIR.rglob(".*.jod_tmp"))
    assert orphans == [], f"Shadow files órfãos: {orphans}"


# ---------------------------------------------------------------------------
# 6. Regressão de _async_guardian_check após refatoração
# ---------------------------------------------------------------------------
def test_guardian_check_approved_regression(agents):
    r = httpx.post(f"{BASE_URL}/agents/{agents['guardian_id']}/guardian/check",
                   json={"action": "read_file"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_guardian_check_blocked_regression(agents):
    r = httpx.post(f"{BASE_URL}/agents/{agents['guardian_id']}/guardian/check",
                   json={"action": "modify_manifest"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"


def test_guardian_check_needs_approval_regression(agents):
    r = httpx.post(f"{BASE_URL}/agents/{agents['guardian_id']}/guardian/check",
                   json={"action": "git_push"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "needs_approval"
