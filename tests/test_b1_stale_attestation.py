import httpx
import json
import pytest
import sqlite3
from pathlib import Path

BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
DB_PATH  = "/home/wsl/JOD_ROBO/jod_robo.db"
BASE_DIR = Path("/home/wsl/JOD_ROBO")

_MANIFEST = {
    "allowed_actions": ["write_file", "read_file", "list_dir"],
    "allowed_paths": ["agents/", "scripts/", "templates/", "tests/"],
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

_TARGET_OK       = "tests/b1_ok.txt"
_TARGET_FAIL     = "tests/b1_fail.txt"
_TARGET_CROSS    = "tests/b1_cross.txt"
_TARGET_DRY      = "tests/b1_dry.txt"
_TARGET_NO_GUARD = "tests/b1_no_guardian.txt"


def _db(query: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _get_by_transaction(transaction_id: str) -> dict | None:
    rows = _db(
        "SELECT * FROM integration_audit WHERE transaction_id = ? LIMIT 1",
        (transaction_id,),
    )
    return rows[0] if rows else None


def _get_by_path(
    finalizer_id: str, guardian_id: str, target_path: str
) -> dict | None:
    rows = _db(
        """
        SELECT * FROM integration_audit
        WHERE finalizer_id = ?
          AND guardian_id  = ?
          AND action       = 'write_file'
          AND target_path  = ?
        ORDER BY rowid DESC LIMIT 1
        """,
        (finalizer_id, guardian_id, target_path),
    )
    return rows[0] if rows else None


def _get_guardian_cross_trail(
    guardian_id: str, transaction_id: str
) -> dict | None:
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


def _assert_no_shadow_for(target_path: str) -> None:
    basename = Path(target_path).name
    shadows = list(BASE_DIR.rglob(f".{basename}.*.jod_tmp"))
    assert shadows == [], f"shadow órfão encontrado para {target_path}: {shadows}"


def _set_io_fail(target_path: str) -> None:
    r = httpx.post(
        f"{BASE_URL}/test/io-fail/set",
        headers=HEADERS,
        params={"target_path": target_path},
    )
    assert r.status_code == 200, (
        f"set io-fail falhou ({r.status_code}): {r.text}\n"
        f"Servidor rodando com JOD_ENV=test?"
    )


def _clear_io_fail() -> None:
    r = httpx.post(f"{BASE_URL}/test/io-fail/clear", headers=HEADERS)
    assert r.status_code == 200, f"clear io-fail falhou: {r.text}"


@pytest.fixture(scope="module")
def guardian_id():
    r = httpx.post(
        f"{BASE_URL}/agents/guardian",
        headers=HEADERS,
        json={"name": "guardian-b1-test"},
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
        json={"name": "finalizer-b1-test", "manifest": _MANIFEST},
    )
    assert r.status_code == 200, f"criar finalizer falhou: {r.text}"
    fid = r.json()["agent_id"]

    r = httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/validate", headers=HEADERS)
    assert r.status_code == 200, f"validar finalizer falhou: {r.text}"

    r = httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/activate", headers=HEADERS)
    assert r.status_code == 200, f"ativar finalizer falhou: {r.text}"

    yield fid


@pytest.fixture(autouse=True)
def limpar_hook():
    _clear_io_fail()
    yield
    _clear_io_fail()


def test_io_committed_true_after_successful_write(finalizer_id, guardian_id):
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_OK,
            "payload": "conteudo ok b1",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "applied"

    transaction_id = r.json()["evidence"]["guardian_transaction_id"]
    rec = _get_by_transaction(transaction_id)

    assert rec is not None
    assert rec["io_committed"] == 1
    assert rec["io_finalized_at"] is not None
    assert rec["io_failure_reason"] is None
    assert rec["guardian_status"] == "approved"
    assert (BASE_DIR / _TARGET_OK).exists()
    _assert_no_shadow_for(_TARGET_OK)


def test_io_committed_false_when_write_fails(finalizer_id, guardian_id):
    _set_io_fail(_TARGET_FAIL)

    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_FAIL,
            "payload": "vai falhar",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 500, (
        f"esperado 500, obtido {r.status_code}: {r.text}"
    )

    rec = _get_by_path(finalizer_id, guardian_id, _TARGET_FAIL)

    assert rec is not None
    assert rec["io_committed"] == 0
    assert rec["guardian_status"] == "approved"
    assert rec["io_failure_reason"] is not None
    assert "test hook" in rec["io_failure_reason"]
    assert rec["io_finalized_at"] is not None

    assert not (BASE_DIR / _TARGET_FAIL).exists()
    _assert_no_shadow_for(_TARGET_FAIL)


def test_dry_run_never_sets_io_committed(finalizer_id, guardian_id):
    count_before = _db(
        "SELECT COUNT(*) as n FROM integration_audit WHERE io_committed=1"
    )[0]["n"]

    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "dry_run",
            "action": "write_file",
            "target_path": _TARGET_DRY,
            "payload": "dry",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "dry_run_ok"

    count_after = _db(
        "SELECT COUNT(*) as n FROM integration_audit WHERE io_committed=1"
    )[0]["n"]

    assert count_after == count_before


def test_guardian_cross_trail_intact_after_io_failure(finalizer_id, guardian_id):
    _set_io_fail(_TARGET_CROSS)

    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_CROSS,
            "payload": "cross trail",
            "guardian_id": guardian_id,
        },
    )
    assert r.status_code == 500, r.text

    int_rec = _get_by_path(finalizer_id, guardian_id, _TARGET_CROSS)
    assert int_rec is not None
    assert int_rec["guardian_status"] == "approved"
    assert int_rec["io_committed"] == 0
    assert int_rec["io_failure_reason"] is not None

    guard_rec = _get_guardian_cross_trail(
        guardian_id, int_rec["transaction_id"]
    )
    assert guard_rec is not None

    assert not (BASE_DIR / _TARGET_CROSS).exists()
    _assert_no_shadow_for(_TARGET_CROSS)


def test_write_without_guardian_completes(finalizer_id):
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={
            "mode": "apply",
            "action": "write_file",
            "target_path": _TARGET_NO_GUARD,
            "payload": "sem guardian",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True
