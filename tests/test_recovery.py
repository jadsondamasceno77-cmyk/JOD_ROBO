"""
tests/test_recovery.py — Fase 1: Recuperação real pós-queda

T9–T14 : unitários — DB em tempfile, sem servidor
T15    : integração — recovery real com DB injetado (servidor obrigatório)
T16    : integração — fencing real RUNNING+fresco (servidor obrigatório)
"""
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from robo_mae.mission_control import (
    FencingError,
    MissionControl,
    ReconcileDecision,
)

# ---------------------------------------------------------------------------
# Constantes de integração
# ---------------------------------------------------------------------------
BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
DB_PATH  = "/home/wsl/JOD_ROBO/jod_robo.db"
BASE_DIR = Path("/home/wsl/JOD_ROBO")

_MANIFEST = {
    "allowed_actions": ["write_file", "read_file", "list_dir"],
    "allowed_paths":   ["agents/", "scripts/", "templates/", "tests/", "restricted/", "pending/"],
    "forbidden_paths": [
        "app/", "jod_brain/", ".env", "main_fase2.py",
        "jod_brain_main.py", "requirements.txt", "Dockerfile",
        "templates/finalizer_manifest.json",
    ],
    "allowed_hosts":     [],
    "requires_approval": ["run_script", "git_push", "delete_file", "access_secret", "edit_core"],
}


# ---------------------------------------------------------------------------
# Fixture: DB em tempfile (T9–T14, sem servidor)
# ---------------------------------------------------------------------------

def _create_tables(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mission_control (
                mission_id   TEXT    PRIMARY KEY,
                status       TEXT    NOT NULL DEFAULT 'PENDING',
                owner_id     TEXT,
                lock_version INTEGER NOT NULL DEFAULT 0,
                heartbeat_at TEXT,
                claimed_at   TEXT,
                current_step INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mission_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id     TEXT    NOT NULL,
                correlation_id TEXT,
                finalizer_id   TEXT    NOT NULL DEFAULT 'test-fin',
                guardian_id    TEXT,
                action         TEXT    NOT NULL DEFAULT 'write_file',
                target_path    TEXT,
                status         TEXT    NOT NULL,
                io_committed   INTEGER,
                transaction_id TEXT,
                details        TEXT,
                step_index     INTEGER,
                created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()


@pytest.fixture
def db():
    """Fresh SQLite DB em tempfile para cada teste unitário."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    engine  = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    _create_tables(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield Session
    engine.dispose()
    os.unlink(db_path)


# ---------------------------------------------------------------------------
# Fixtures de integração: agentes ativos para T15/T16
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def recovery_finalizer_id():
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        headers=HEADERS,
        json={"name": "finalizer-recovery-test", "manifest": _MANIFEST},
    )
    assert r.status_code == 200, f"criar finalizer falhou: {r.text}"
    fid = r.json()["agent_id"]
    httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/validate", headers=HEADERS)
    httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/activate",  headers=HEADERS)
    return fid


@pytest.fixture(scope="module")
def recovery_guardian_id():
    r = httpx.post(
        f"{BASE_URL}/agents/guardian",
        headers=HEADERS,
        json={"name": "guardian-recovery-test"},
    )
    assert r.status_code == 200, f"criar guardian falhou: {r.text}"
    gid = r.json()["agent_id"]
    httpx.post(f"{BASE_URL}/agents/{gid}/guardian/validate", headers=HEADERS)
    httpx.post(f"{BASE_URL}/agents/{gid}/guardian/activate",  headers=HEADERS)
    return gid


# ---------------------------------------------------------------------------
# Helpers de integração (injeção/leitura direta no DB de produção)
# ---------------------------------------------------------------------------

def _db_inject(query: str, params: dict) -> None:
    con = sqlite3.connect(DB_PATH)
    con.execute(query, params)
    con.commit()
    con.close()


def _db_read(query: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ===========================================================================
# T9 — reconcile: RUNNING+stale, last step RUNNING+io_committed=1 → RESUME(N+1)
# ===========================================================================

def test_t9_reconcile_running_io_committed(db):
    Session = db
    mid = f"t9-{uuid.uuid4()}"

    with Session() as s:
        MissionControl.create(s, mid)

    # Simular crash: RUNNING+stale, step 0 em RUNNING com io_committed=1
    with Session() as s:
        s.execute(text("""
            UPDATE mission_control
            SET status='RUNNING', owner_id='dead-owner', lock_version=1,
                heartbeat_at='2000-01-01T00:00:00', current_step=0
            WHERE mission_id=:mid
        """), {"mid": mid})
        s.execute(text("""
            INSERT INTO mission_log
                (mission_id, finalizer_id, action, status, io_committed, step_index)
            VALUES (:mid, 'fin', 'write_file', 'RUNNING', 1, 0)
        """), {"mid": mid})
        s.commit()

    with Session() as s:
        d = MissionControl.reconcile(s, mid)

    assert d.action           == "RESUME", f"esperado RESUME, obtido {d.action}: {d.reason}"
    assert d.resume_from_step == 1,        f"esperado step 1, obtido {d.resume_from_step}"


# ===========================================================================
# T10 — fencing: lock_version alterado no DB → FencingError
# ===========================================================================

def test_t10_fencing_ownership_lost(db):
    Session = db
    mid = f"t10-{uuid.uuid4()}"

    with Session() as s:
        MissionControl.create(s, mid)

    with Session() as s:
        lv = MissionControl.claim(s, mid, "owner-A")
    assert lv == 1

    # Simular takeover externo: outro processo atualizou lock_version
    with Session() as s:
        s.execute(text("""
            UPDATE mission_control
            SET owner_id='owner-B', lock_version=2
            WHERE mission_id=:mid
        """), {"mid": mid})
        s.commit()

    with Session() as s:
        with pytest.raises(FencingError):
            MissionControl.fence(s, mid, "owner-A", 1)


# ===========================================================================
# T11 — takeover atômico de missão stale + heartbeat do owner antigo retorna False
# ===========================================================================

def test_t11_takeover_stale_and_old_heartbeat_false(db):
    Session = db
    mid = f"t11-{uuid.uuid4()}"

    with Session() as s:
        MissionControl.create(s, mid)

    with Session() as s:
        lv_a = MissionControl.claim(s, mid, "owner-A")
    assert lv_a == 1

    # Tornar heartbeat stale
    with Session() as s:
        s.execute(text("""
            UPDATE mission_control
            SET heartbeat_at='2000-01-01T00:00:00'
            WHERE mission_id=:mid
        """), {"mid": mid})
        s.commit()

    # owner-B faz takeover atômico
    with Session() as s:
        lv_b = MissionControl.takeover(s, mid, "owner-B")
    assert lv_b == 2, f"esperado lock_version=2, obtido {lv_b}"

    # owner-A heartbeat retorna False (ownership perdida)
    with Session() as s:
        alive = MissionControl.heartbeat(s, mid, "owner-A", lv_a)
    assert alive is False

    # owner-B fence passa
    with Session() as s:
        MissionControl.fence(s, mid, "owner-B", lv_b)


# ===========================================================================
# T12 — reconcile: RUNNING+stale, io_committed=0 → QUARANTINE
# ===========================================================================

def test_t12_reconcile_running_io_ambiguous(db):
    Session = db
    mid = f"t12-{uuid.uuid4()}"

    with Session() as s:
        MissionControl.create(s, mid)

    with Session() as s:
        s.execute(text("""
            UPDATE mission_control
            SET status='RUNNING', owner_id='dead-owner', lock_version=1,
                heartbeat_at='2000-01-01T00:00:00'
            WHERE mission_id=:mid
        """), {"mid": mid})
        s.execute(text("""
            INSERT INTO mission_log
                (mission_id, finalizer_id, action, status, io_committed, step_index)
            VALUES (:mid, 'fin', 'write_file', 'RUNNING', 0, 0)
        """), {"mid": mid})
        s.commit()

    with Session() as s:
        d = MissionControl.reconcile(s, mid)

    assert d.action == "QUARANTINE", f"esperado QUARANTINE, obtido {d.action}: {d.reason}"


# ===========================================================================
# T13 — heartbeat válido: owner ativo → True
# ===========================================================================

def test_t13_heartbeat_valid_owner(db):
    Session = db
    mid = f"t13-{uuid.uuid4()}"

    with Session() as s:
        MissionControl.create(s, mid)

    with Session() as s:
        lv = MissionControl.claim(s, mid, "owner-X")

    with Session() as s:
        alive = MissionControl.heartbeat(s, mid, "owner-X", lv)
    assert alive is True


# ===========================================================================
# T14 — claim falha se RUNNING com heartbeat fresco; takeover também falha
# ===========================================================================

def test_t14_claim_and_takeover_fail_if_running_fresh(db):
    Session = db
    mid = f"t14-{uuid.uuid4()}"

    with Session() as s:
        MissionControl.create(s, mid)

    with Session() as s:
        lv_a = MissionControl.claim(s, mid, "owner-A")
    assert lv_a == 1

    # owner-B: claim falha — missão não está mais PENDING
    with Session() as s:
        lv_b = MissionControl.claim(s, mid, "owner-B")
    assert lv_b is None, "claim deve falhar para missão RUNNING"

    # owner-B: takeover falha — heartbeat é fresco
    with Session() as s:
        lv_b2 = MissionControl.takeover(s, mid, "owner-B")
    assert lv_b2 is None, "takeover deve falhar com heartbeat fresco"


# ===========================================================================
# T15 — recovery real: DB injetado com crash, missão retoma de step 2
#       (servidor obrigatório com JOD_ENV=test)
# ===========================================================================

def test_t15_real_recovery_resumes_from_step2(
    recovery_finalizer_id, recovery_guardian_id
):
    """
    Simula crash após step 1 (RUNNING+io_committed=1).
    O executor deve:
      - detectar RUNNING+stale via reconcile → RESUME(2)
      - takeover com novo owner_id
      - reparar step 1: RUNNING → applied
      - pular steps 0 e 1
      - executar step 2
      - marcar COMPLETED
    Prova de não-duplicação: arquivos s0 e s1 não existem (não re-executados).
    """
    mid = f"t15-{uuid.uuid4()}"
    fid = recovery_finalizer_id
    gid = recovery_guardian_id

    s0 = "tests/t15_s0.txt"
    s1 = "tests/t15_s1.txt"
    s2 = "tests/t15_s2.txt"

    # Limpar artefatos de corridas anteriores
    for p in [s0, s1, s2]:
        (BASE_DIR / p).unlink(missing_ok=True)

    # Injetar estado de crash: RUNNING+stale, current_step=1
    _db_inject("""
        INSERT OR REPLACE INTO mission_control
            (mission_id, status, owner_id, lock_version,
             heartbeat_at, claimed_at, current_step, created_at)
        VALUES
            (:mid, 'RUNNING', 'crashed-owner', 1,
             '2000-01-01T00:00:00', '2000-01-01T00:00:00', 1, '2000-01-01T00:00:00')
    """, {"mid": mid})

    # step 0: já aplicado (histórico fake)
    _db_inject("""
        INSERT INTO mission_log
            (mission_id, correlation_id, finalizer_id, guardian_id,
             action, target_path, status, io_committed, step_index)
        VALUES
            (:mid, :mid, :fid, :gid,
             'write_file', :s0, 'applied', 1, 0)
    """, {"mid": mid, "fid": fid, "gid": gid, "s0": s0})

    # step 1: crash em RUNNING com io_committed=1 (IO ocorreu, finish_step não chegou)
    _db_inject("""
        INSERT INTO mission_log
            (mission_id, correlation_id, finalizer_id, guardian_id,
             action, target_path, status, io_committed, step_index)
        VALUES
            (:mid, :mid, :fid, :gid,
             'write_file', :s1, 'RUNNING', 1, 1)
    """, {"mid": mid, "fid": fid, "gid": gid, "s1": s1})

    # POST /missions/run com o mesmo mission_id e 3 steps
    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mid,
            "finalizer_id": fid,
            "guardian_id":  gid,
            "steps": [
                {"action": "write_file", "target_path": s0,
                 "payload": "step0-crashed", "mode": "apply"},
                {"action": "write_file", "target_path": s1,
                 "payload": "step1-crashed", "mode": "apply"},
                {"action": "write_file", "target_path": s2,
                 "payload": "step2-recovery", "mode": "apply"},
            ],
        },
        timeout=30.0,
    )
    assert r.status_code == 200, f"esperado 200, obtido {r.status_code}: {r.text}"

    body = r.json()
    assert body["summary"]["success"] is True, (
        f"missão deve ter sucesso após recovery: {body['summary']}"
    )

    # Prova de não-duplicação: s0 e s1 não foram re-escritos
    assert (BASE_DIR / s2).exists(),      "tests/t15_s2.txt deve ter sido criado por step 2"
    assert not (BASE_DIR / s0).exists(),  "tests/t15_s0.txt não deve ter sido re-executado"
    assert not (BASE_DIR / s1).exists(),  "tests/t15_s1.txt não deve ter sido re-executado"

    # step 1 reparado: RUNNING → applied
    logs = _db_read(
        "SELECT status, step_index FROM mission_log WHERE mission_id=? AND step_index=1",
        (mid,),
    )
    assert logs,                           "entrada do step 1 não encontrada em mission_log"
    assert logs[0]["status"] == "applied", (
        f"step 1 deve estar 'applied' após repair, obtido: {logs[0]['status']}"
    )

    # mission_control: COMPLETED, owner diferente do crashado
    mc = _db_read(
        "SELECT status, owner_id FROM mission_control WHERE mission_id=?",
        (mid,),
    )
    assert mc[0]["status"]   == "COMPLETED",     f"esperado COMPLETED, obtido {mc[0]['status']}"
    assert mc[0]["owner_id"] != "crashed-owner", "owner_id não deve ser 'crashed-owner'"


# ===========================================================================
# T16 — fencing real: missão RUNNING+fresco → HTTP 500, DB intacto
#       (servidor obrigatório)
# ===========================================================================

def test_t16_real_fencing_running_fresh_blocks_execution(
    recovery_finalizer_id, recovery_guardian_id
):
    """
    Missão em RUNNING com heartbeat fresco.
    Nova tentativa de /missions/run deve retornar HTTP 500 (NOOP do reconcile).
    DB deve permanecer intacto: owner e lock_version inalterados.
    """
    mid = f"t16-{uuid.uuid4()}"
    fid = recovery_finalizer_id
    gid = recovery_guardian_id
    now = datetime.utcnow().isoformat()

    # Limpar artefato caso exista
    (BASE_DIR / "tests/t16_should_not_exist.txt").unlink(missing_ok=True)

    # Injetar missão RUNNING com heartbeat fresco
    _db_inject("""
        INSERT OR REPLACE INTO mission_control
            (mission_id, status, owner_id, lock_version,
             heartbeat_at, claimed_at, current_step, created_at)
        VALUES
            (:mid, 'RUNNING', 'live-owner', 1,
             :now, :now, 0, :now)
    """, {"mid": mid, "now": now})

    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mid,
            "finalizer_id": fid,
            "guardian_id":  gid,
            "steps": [
                {"action": "write_file",
                 "target_path": "tests/t16_should_not_exist.txt",
                 "payload": "não deve ser escrito", "mode": "apply"},
            ],
        },
        timeout=30.0,
    )
    assert r.status_code == 500, (
        f"esperado 500 (NOOP/fencing), obtido {r.status_code}: {r.text}"
    )

    # DB intacto: owner e lock_version inalterados
    mc = _db_read(
        "SELECT owner_id, lock_version, status FROM mission_control WHERE mission_id=?",
        (mid,),
    )
    assert mc[0]["owner_id"]    == "live-owner", "owner_id foi alterado indevidamente"
    assert mc[0]["lock_version"] == 1,           "lock_version foi alterado indevidamente"
    assert mc[0]["status"]       == "RUNNING",   "status foi alterado indevidamente"

    # arquivo não foi escrito
    assert not (BASE_DIR / "tests/t16_should_not_exist.txt").exists(), (
        "arquivo não deve ter sido escrito"
    )
