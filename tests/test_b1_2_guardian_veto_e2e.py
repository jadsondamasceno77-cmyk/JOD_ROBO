import httpx
import json
import pytest
import sqlite3
from pathlib import Path

BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
_ROOT    = Path(__file__).parent.parent
DB_PATH  = str(_ROOT / "jod_robo.db")
BASE_DIR = _ROOT

_MANIFEST_B12 = {
    "allowed_actions": ["write_file", "read_file", "list_dir"],
    "allowed_paths": ["agents/", "scripts/", "templates/", "tests/", "restricted/", "pending/"],
    "forbidden_paths": [
        "app/",
        "jod_brain/",
        ".env",
        "main_fase2.py",
        "jod_brain_main.py",
        "requirements.txt",
        "Dockerfile",
        "templates/finalizer_manifest.json",
    ],
    "allowed_hosts": [],
    "requires_approval": [
        "run_script",
        "git_push",
        "delete_file",
        "access_secret",
        "edit_core",
    ],
}

_TARGET_BLOCKED        = "restricted/b12_blocked.txt"
_TARGET_NEEDS_APPROVAL = "pending/b12_pending.txt"
_TARGET_APPROVED       = "tests/b12_approved.txt"
_TARGET_CROSS          = "restricted/b12_cross.txt"


def _db(query: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _get_integration_by_transaction(transaction_id: str) -> dict | None:
    rows = _db(
        "SELECT * FROM integration_audit WHERE transaction_id = ? LIMIT 1",
        (transaction_id,),
    )
    return rows[0] if rows else None


def _get_guardian_cross_trail(guardian_id: str, transaction_id: str) -> dict | None:
    rows = _db(
        """
        SELECT * FROM guardian_audit
        WHERE agent_id = ?
          AND status LIKE 'attested:%'
        ORDER BY rowid DESC
        """,
        (guardian_id,),
    )
    for row in rows:
        try:
            details = json.loads(row.get("details") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if details.get("transaction_id") == transaction_id:
            return row
    return None


def _get_finalizer_audit_by_transaction(transaction_id: str) -> dict | None:
    rows = _db(
        "SELECT * FROM finalizer_audit WHERE details LIKE ? ORDER BY rowid DESC LIMIT 1",
        (f"%{transaction_id}%",),
    )
    return rows[0] if rows else None


def _assert_no_shadow_for(target_path: str) -> None:
    basename = Path(target_path).name
    shadows = list(BASE_DIR.rglob(f".{basename}.*.jod_tmp"))
    assert shadows == [], f"shadow órfão encontrado para {target_path}: {shadows}"


@pytest.fixture(scope="module")
def guardian_id():
    r = httpx.post(
        f"{BASE_URL}/agents/guardian",
        headers=HEADERS,
        json={"name": "guardian-b12-test"},
    )
    assert r.status_code == 200, f"criar guardian falhou: {r.text}"
    gid = r.json()["agent_id"]

    r = httpx.post(f"{BASE_URL}/agents/{gid}/guardian/validate", headers=HEADERS)
    assert r.status_code == 200, f"validar guardian falhou: {r.text}"

    r = httpx.post(f"{BASE_URL}/agents/{gid}/guardian/activate", headers=HEADERS)
    assert r.status_code == 200, f"ativar guardian falhou: {r.text}"

    yield gid


@pytest.fixture(scope="module")
def finalizer_id():
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        headers=HEADERS,
        json={"name": "finalizer-b12-test", "manifest": _MANIFEST_B12},
    )
    assert r.status_code == 200, f"criar finalizer falhou: {r.text}"
    fid = r.json()["agent_id"]

    r = httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/validate", headers=HEADERS)
    assert r.status_code == 200, f"validar finalizer falhou: {r.text}"

    r = httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/activate", headers=HEADERS)
    assert r.status_code == 200, f"ativar finalizer falhou: {r.text}"

    yield fid


def test_veto_blocked_returns_403(finalizer_id, guardian_id):
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_BLOCKED,
            "payload": "bloqueado",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 403, f"esperado 403, obtido {r.status_code}: {r.text}"
    detail = r.json()["detail"]
    assert detail["guardian_status"] == "blocked"
    transaction_id = detail["guardian_transaction_id"]

    # arquivo não foi escrito
    assert not (BASE_DIR / _TARGET_BLOCKED).exists()
    _assert_no_shadow_for(_TARGET_BLOCKED)

    # integration_audit: guardian_status=blocked, io nunca executado
    int_rec = _get_integration_by_transaction(transaction_id)
    assert int_rec is not None
    assert int_rec["guardian_status"] == "blocked"
    assert int_rec["io_committed"] == 0
    assert int_rec["io_finalized_at"] is None

    # guardian_audit: trilha cruzada com mesmo transaction_id
    guard_rec = _get_guardian_cross_trail(guardian_id, transaction_id)
    assert guard_rec is not None
    assert guard_rec["status"] == "attested:blocked"

    # finalizer_audit: forbidden com reason=guardian_veto:blocked
    fin_rec = _get_finalizer_audit_by_transaction(transaction_id)
    assert fin_rec is not None
    assert fin_rec["status"] == "forbidden"
    fin_details = json.loads(fin_rec["details"])
    assert fin_details.get("reason") == "guardian_veto:blocked"


def test_veto_needs_approval_returns_403(finalizer_id, guardian_id):
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_NEEDS_APPROVAL,
            "payload": "pendente",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 403, f"esperado 403, obtido {r.status_code}: {r.text}"
    detail = r.json()["detail"]
    assert detail["guardian_status"] == "needs_approval"
    transaction_id = detail["guardian_transaction_id"]

    # arquivo não foi escrito
    assert not (BASE_DIR / _TARGET_NEEDS_APPROVAL).exists()
    _assert_no_shadow_for(_TARGET_NEEDS_APPROVAL)

    # integration_audit: guardian_status=needs_approval, io nunca executado
    int_rec = _get_integration_by_transaction(transaction_id)
    assert int_rec is not None
    assert int_rec["guardian_status"] == "needs_approval"
    assert int_rec["io_committed"] == 0
    assert int_rec["io_finalized_at"] is None

    # guardian_audit: trilha cruzada
    guard_rec = _get_guardian_cross_trail(guardian_id, transaction_id)
    assert guard_rec is not None
    assert guard_rec["status"] == "attested:needs_approval"

    # finalizer_audit: forbidden com reason=guardian_veto:needs_approval
    fin_rec = _get_finalizer_audit_by_transaction(transaction_id)
    assert fin_rec is not None
    assert fin_rec["status"] == "forbidden"
    fin_details = json.loads(fin_rec["details"])
    assert fin_details.get("reason") == "guardian_veto:needs_approval"


def test_approved_path_writes_file(finalizer_id, guardian_id):
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_APPROVED,
            "payload": "aprovado b12",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "applied"
    transaction_id = r.json()["evidence"]["guardian_transaction_id"]

    int_rec = _get_integration_by_transaction(transaction_id)
    assert int_rec is not None
    assert int_rec["guardian_status"] == "approved"
    assert int_rec["io_committed"] == 1
    assert (BASE_DIR / _TARGET_APPROVED).exists()
    _assert_no_shadow_for(_TARGET_APPROVED)


def test_transaction_id_consistent_across_tables(finalizer_id, guardian_id):
    """O mesmo transaction_id deve aparecer em response, integration_audit,
    guardian_audit e finalizer_audit — inclusive em caso de veto."""
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_CROSS,
            "payload": "cross",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 403, r.text
    transaction_id = r.json()["detail"]["guardian_transaction_id"]
    assert transaction_id, "transaction_id ausente na resposta 403"

    int_rec = _get_integration_by_transaction(transaction_id)
    assert int_rec is not None, "integration_audit sem registro para este transaction_id"
    assert int_rec["transaction_id"] == transaction_id

    guard_rec = _get_guardian_cross_trail(guardian_id, transaction_id)
    assert guard_rec is not None, "guardian_audit sem cross-trail para este transaction_id"

    fin_rec = _get_finalizer_audit_by_transaction(transaction_id)
    assert fin_rec is not None, "finalizer_audit sem registro para este transaction_id"

    assert not (BASE_DIR / _TARGET_CROSS).exists()
    _assert_no_shadow_for(_TARGET_CROSS)
