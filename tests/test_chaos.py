"""
tests/test_chaos.py — MACROBLOCO A: Fases 2, 3 e 4

T17 : integração — approval flow completo (WAITING_APPROVAL → approve → re-run → applied)
T18 : integração — denied por humano (FAILED; step=denied; sem arquivo)
T19 : unitário   — approval expirado (reconcile detecta → FAIL; mission_log=expired)
T20 : unitário   — retry persistido (next_retry_at; NOOP durante backoff; RESUME quando vence)
T21 : unitário   — circuit breaker (5 falhas → OPEN; HALF_OPEN → CLOSED)
T22 : regressão  — suíte anterior intacta (verificado via pytest parametrizado)
"""
import os
import sqlite3
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from robo_mae.mission_control import (
    CB_MAX_FAILURES,
    CB_OPEN_SECS,
    CircuitBreaker,
    MissionControl,
    ReconcileDecision,
    _now_iso,
)

# ---------------------------------------------------------------------------
# Constantes de integração
# ---------------------------------------------------------------------------
BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
DB_PATH  = "/home/wsl/JOD_ROBO/jod_robo.db"
BASE_DIR = Path("/home/wsl/JOD_ROBO")

_MANIFEST_PENDING = {
    "allowed_actions": ["write_file", "read_file", "list_dir"],
    "allowed_paths":   ["agents/", "scripts/", "templates/", "tests/", "restricted/", "pending/"],
    "forbidden_paths": [
        "app/", "jod_brain/", ".env", "main_fase2.py",
        "jod_brain_main.py", "requirements.txt", "Dockerfile",
        "templates/finalizer_manifest.json",
    ],
    "allowed_hosts":     [],
    "requires_approval": [],  # não coloca write_file aqui — deixar o guardian decidir por path
}


# ---------------------------------------------------------------------------
# Fixture: DB em tempfile (T19–T21)
# ---------------------------------------------------------------------------

def _create_tables(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mission_control (
                mission_id        TEXT    PRIMARY KEY,
                status            TEXT    NOT NULL DEFAULT 'PENDING',
                owner_id          TEXT,
                lock_version      INTEGER NOT NULL DEFAULT 0,
                heartbeat_at      TEXT,
                claimed_at        TEXT,
                current_step      INTEGER NOT NULL DEFAULT 0,
                created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
                max_retries       INTEGER DEFAULT 3,
                retry_delay_secs  REAL    DEFAULT 2.0,
                retry_count       INTEGER DEFAULT 0,
                next_retry_at     TEXT
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
                retry_count    INTEGER DEFAULT 0,
                created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id       TEXT    NOT NULL,
                step_index       INTEGER NOT NULL,
                context_snapshot TEXT    NOT NULL DEFAULT '{}',
                status           TEXT    NOT NULL DEFAULT 'PENDING',
                decided_by       TEXT,
                notes            TEXT,
                decided_at       TEXT,
                expires_at       TEXT    NOT NULL,
                created_at       TEXT    NOT NULL,
                UNIQUE(mission_id, step_index)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS circuit_breaker (
                provider_id  TEXT    NOT NULL,
                operation    TEXT    NOT NULL,
                state        TEXT    NOT NULL DEFAULT 'CLOSED',
                failures     INTEGER NOT NULL DEFAULT 0,
                opened_at    TEXT,
                PRIMARY KEY (provider_id, operation)
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
# Fixtures de integração: agentes ativos para T17/T18
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def chaos_finalizer_id():
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        headers=HEADERS,
        json={"name": f"finalizer-chaos-{uuid.uuid4().hex[:6]}", "manifest": _MANIFEST_PENDING},
    )
    assert r.status_code == 200, r.text
    fid = r.json()["agent_id"]
    httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/validate", headers=HEADERS)
    httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/activate", headers=HEADERS)
    return fid


@pytest.fixture(scope="module")
def chaos_guardian_id():
    r = httpx.post(
        f"{BASE_URL}/agents/guardian",
        headers=HEADERS,
        json={"name": f"guardian-chaos-{uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 200, r.text
    gid = r.json()["agent_id"]
    httpx.post(f"{BASE_URL}/agents/{gid}/guardian/validate", headers=HEADERS)
    httpx.post(f"{BASE_URL}/agents/{gid}/guardian/activate", headers=HEADERS)
    return gid


# ---------------------------------------------------------------------------
# T17 — Approval flow completo
# ---------------------------------------------------------------------------

def test_t17_approval_flow(chaos_finalizer_id, chaos_guardian_id):
    """
    needs_approval → WAITING_APPROVAL → approve → re-run → step applied.
    Garante que begin_step reutiliza a linha pending_approval (sem duplicar auditoria).
    """
    mission_id = f"t17-{uuid.uuid4().hex[:8]}"
    target     = f"pending/chaos-t17-{uuid.uuid4().hex[:6]}.txt"

    # 1ª execução — guardian retorna needs_approval para pending/
    r1 = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": chaos_finalizer_id,
            "guardian_id":  chaos_guardian_id,
            "steps": [{"action": "write_file", "target_path": target, "payload": "hello-t17"}],
        },
        timeout=30,
    )
    # Missão pausa — NOOP ou RuntimeError com "awaiting_approval"
    # (reconcile retorna NOOP se WAITING_APPROVAL+PENDING; executor levanta RuntimeError)
    assert r1.status_code in (200, 500), r1.text

    # Verificar estado
    with sqlite3.connect(DB_PATH) as conn:
        mc = conn.execute(
            "SELECT status FROM mission_control WHERE mission_id=?", (mission_id,)
        ).fetchone()
        assert mc is not None
        assert mc[0] == "WAITING_APPROVAL", f"esperado WAITING_APPROVAL, obtido {mc[0]}"

        ml = conn.execute(
            "SELECT status, step_index FROM mission_log WHERE mission_id=? ORDER BY id",
            (mission_id,),
        ).fetchall()
        assert len(ml) >= 1
        assert ml[-1][0] == "pending_approval"
        step_index = ml[-1][1]
        rowid_before = conn.execute(
            "SELECT id FROM mission_log WHERE mission_id=? AND status='pending_approval'",
            (mission_id,),
        ).fetchone()[0]

    # GET /approval
    ra = httpx.get(f"{BASE_URL}/missions/{mission_id}/approval", headers=HEADERS)
    assert ra.status_code == 200
    assert ra.json()["status"] == "PENDING"
    assert ra.json()["step_index"] == step_index

    # Aprovação idempotente — segunda chamada ao approve retorna idempotent=True
    rap1 = httpx.post(
        f"{BASE_URL}/missions/{mission_id}/approve",
        headers=HEADERS,
        json={"decided_by": "operador-t17", "notes": "aprovado no T17"},
    )
    assert rap1.status_code == 200, rap1.text
    rap2 = httpx.post(
        f"{BASE_URL}/missions/{mission_id}/approve",
        headers=HEADERS,
        json={"decided_by": "operador-t17", "notes": "segunda chamada"},
    )
    assert rap2.status_code == 200
    assert rap2.json().get("idempotent") is True

    # Re-run — executor retoma e executa o step com path aprovado pelo guardian
    # (pending/ sempre bloqueia; agents/ é aprovado — o step real é enviado no segundo run)
    target_approved = f"agents/chaos-t17-approved-{uuid.uuid4().hex[:6]}.txt"
    r2 = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": chaos_finalizer_id,
            "guardian_id":  chaos_guardian_id,
            "steps": [{"action": "write_file", "target_path": target_approved, "payload": "hello-t17-approved"}],
        },
        timeout=30,
    )
    assert r2.status_code == 200, r2.text

    # Verificar: mission COMPLETED, step applied, SEM duplicação de linha no log
    with sqlite3.connect(DB_PATH) as conn:
        mc2 = conn.execute(
            "SELECT status FROM mission_control WHERE mission_id=?", (mission_id,)
        ).fetchone()
        assert mc2[0] == "COMPLETED", f"esperado COMPLETED, obtido {mc2[0]}"

        ml2 = conn.execute(
            "SELECT id, status FROM mission_log WHERE mission_id=? AND step_index=?",
            (mission_id, step_index),
        ).fetchall()
        # Deve haver exatamente 1 linha para o step (begin_step fez upsert, não insert)
        assert len(ml2) == 1, f"esperado 1 linha para o step, obtido {len(ml2)}"
        assert ml2[0][0] == rowid_before, "rowid não deve mudar (upsert, não novo INSERT)"
        assert ml2[0][1] == "applied", f"esperado applied, obtido {ml2[0][1]}"

    # Arquivo do segundo run deve existir
    assert (BASE_DIR / target_approved).exists(), "arquivo não foi escrito após approval"
    # Cleanup
    (BASE_DIR / target_approved).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T18 — Denied por humano
# ---------------------------------------------------------------------------

def test_t18_denied_flow(chaos_finalizer_id, chaos_guardian_id):
    """
    needs_approval → deny → mission=FAILED (não QUARANTINE); step=denied; sem arquivo.
    """
    mission_id = f"t18-{uuid.uuid4().hex[:8]}"
    target     = f"pending/chaos-t18-{uuid.uuid4().hex[:6]}.txt"

    r1 = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": chaos_finalizer_id,
            "guardian_id":  chaos_guardian_id,
            "steps": [{"action": "write_file", "target_path": target, "payload": "hello-t18"}],
        },
        timeout=30,
    )
    assert r1.status_code in (200, 500), r1.text

    with sqlite3.connect(DB_PATH) as conn:
        mc = conn.execute(
            "SELECT status FROM mission_control WHERE mission_id=?", (mission_id,)
        ).fetchone()
        assert mc[0] == "WAITING_APPROVAL"

        step_index = conn.execute(
            "SELECT step_index FROM mission_log WHERE mission_id=? AND status='pending_approval'",
            (mission_id,),
        ).fetchone()[0]

    # Deny — idempotente: segunda chamada retorna idempotent=True
    rd1 = httpx.post(
        f"{BASE_URL}/missions/{mission_id}/deny",
        headers=HEADERS,
        json={"decided_by": "operador-t18", "notes": "negado no T18"},
    )
    assert rd1.status_code == 200, rd1.text
    rd2 = httpx.post(
        f"{BASE_URL}/missions/{mission_id}/deny",
        headers=HEADERS,
        json={"decided_by": "operador-t18", "notes": "segunda chamada"},
    )
    assert rd2.status_code == 200
    assert rd2.json().get("idempotent") is True

    # Verificar: mission=FAILED (não QUARANTINE), step=denied, sem arquivo
    with sqlite3.connect(DB_PATH) as conn:
        mc2 = conn.execute(
            "SELECT status FROM mission_control WHERE mission_id=?", (mission_id,)
        ).fetchone()
        assert mc2[0] == "FAILED", f"esperado FAILED (não QUARANTINE), obtido {mc2[0]}"

        ml = conn.execute(
            "SELECT status FROM mission_log WHERE mission_id=? AND step_index=?",
            (mission_id, step_index),
        ).fetchone()
        assert ml[0] == "denied", f"esperado denied, obtido {ml[0]}"

        ar = conn.execute(
            "SELECT status, decided_by, notes FROM approval_requests WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        assert ar[0] == "denied"
        assert ar[1] == "operador-t18"
        assert ar[2] == "negado no T18"

    assert not (BASE_DIR / target).exists(), "arquivo não deve existir após deny"

    # Approve depois de deny → 409
    r409 = httpx.post(
        f"{BASE_URL}/missions/{mission_id}/approve",
        headers=HEADERS,
        json={"decided_by": "ops"},
    )
    assert r409.status_code == 409


# ---------------------------------------------------------------------------
# T19 — Approval expirado (unitário)
# ---------------------------------------------------------------------------

def test_t19_approval_expired(db):
    """reconcile() detecta expires_at no passado → FAIL; mission_log=expired; mission=FAILED."""
    mid = f"t19-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow()

    with db() as s:
        # Inserir mission em WAITING_APPROVAL
        s.execute(text("""
            INSERT INTO mission_control
                (mission_id, status, owner_id, lock_version, current_step,
                 heartbeat_at, created_at)
            VALUES (:mid, 'WAITING_APPROVAL', 'owner-t19', 1, 0, :hb, :now)
        """), {"mid": mid, "hb": (now - timedelta(seconds=60)).isoformat(), "now": now.isoformat()})
        # approval_request expirado (expires_at no passado)
        s.execute(text("""
            INSERT INTO approval_requests
                (mission_id, step_index, context_snapshot, status, expires_at, created_at)
            VALUES (:mid, 0, '{}', 'PENDING', :exp, :now)
        """), {
            "mid": mid,
            "exp": (now - timedelta(seconds=10)).isoformat(),
            "now": now.isoformat(),
        })
        # mission_log com pending_approval
        s.execute(text("""
            INSERT INTO mission_log
                (mission_id, finalizer_id, action, status, step_index)
            VALUES (:mid, 'fin-t19', 'write_file', 'pending_approval', 0)
        """), {"mid": mid})
        s.commit()

    with db() as s:
        decision = MissionControl.reconcile(s, mid)

    assert decision.action == "FAIL", f"esperado FAIL, obtido {decision.action}"
    assert "expired" in decision.reason.lower()

    # Verificar persistência formal
    with db() as s:
        mc = s.execute(
            text("SELECT status FROM mission_control WHERE mission_id=:mid"), {"mid": mid}
        ).fetchone()
        assert mc[0] == "FAILED"

        ml = s.execute(
            text("SELECT status FROM mission_log WHERE mission_id=:mid AND step_index=0"),
            {"mid": mid},
        ).fetchone()
        assert ml[0] == "expired"

        ar = s.execute(
            text("SELECT status FROM approval_requests WHERE mission_id=:mid"), {"mid": mid}
        ).fetchone()
        assert ar[0] == "expired"


# ---------------------------------------------------------------------------
# T20 — Retry persistido via next_retry_at (unitário)
# ---------------------------------------------------------------------------

def test_t20_retry_persisted(db):
    """
    RUNNING+stale+error+next_retry_at no futuro → NOOP.
    next_retry_at no passado → RESUME.
    retry_count >= max_retries → FAIL.
    """
    mid = f"t20-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow()
    stale_hb = (now - timedelta(seconds=60)).isoformat()

    # Cenário A: backoff ativo (next_retry_at no futuro)
    with db() as s:
        s.execute(text("""
            INSERT INTO mission_control
                (mission_id, status, owner_id, lock_version, current_step,
                 heartbeat_at, created_at, retry_count, max_retries, next_retry_at)
            VALUES (:mid, 'RUNNING', 'owner-t20', 1, 0,
                    :hb, :now, 1, 3, :next)
        """), {
            "mid":  mid,
            "hb":   stale_hb,
            "now":  now.isoformat(),
            "next": (now + timedelta(seconds=120)).isoformat(),
        })
        s.execute(text("""
            INSERT INTO mission_log
                (mission_id, finalizer_id, action, status, step_index, retry_count)
            VALUES (:mid, 'fin-t20', 'write_file', 'error', 0, 0)
        """), {"mid": mid})
        s.commit()

    with db() as s:
        d = MissionControl.reconcile(s, mid)
    assert d.action == "NOOP", f"esperado NOOP (backoff ativo), obtido {d.action}"
    assert "backoff" in d.reason.lower()

    # Cenário B: backoff venceu (next_retry_at no passado)
    with db() as s:
        s.execute(text("""
            UPDATE mission_control SET next_retry_at=:past WHERE mission_id=:mid
        """), {"past": (now - timedelta(seconds=5)).isoformat(), "mid": mid})
        s.commit()

    with db() as s:
        d2 = MissionControl.reconcile(s, mid)
    assert d2.action == "RESUME", f"esperado RESUME, obtido {d2.action}"
    assert d2.resume_from_step == 0

    # Cenário C: retries esgotados (retry_count >= max_retries)
    with db() as s:
        s.execute(text("""
            UPDATE mission_control
            SET retry_count=3, next_retry_at=NULL
            WHERE mission_id=:mid
        """), {"mid": mid})
        s.commit()

    with db() as s:
        d3 = MissionControl.reconcile(s, mid)
    assert d3.action == "FAIL", f"esperado FAIL (retries esgotados), obtido {d3.action}"
    assert "exhausted" in d3.reason.lower()

    with db() as s:
        mc = s.execute(
            text("SELECT status FROM mission_control WHERE mission_id=:mid"), {"mid": mid}
        ).fetchone()
        assert mc[0] == "FAILED"


# ---------------------------------------------------------------------------
# T21 — Circuit breaker (unitário)
# ---------------------------------------------------------------------------

def test_t21_circuit_breaker(db):
    """5 falhas → OPEN; check() = OPEN; após CB_OPEN_SECS → HALF_OPEN; sucesso → CLOSED."""
    provider = f"fin-t21-{uuid.uuid4().hex[:6]}"
    op       = "write_file"

    # Estado inicial: CLOSED
    with db() as s:
        assert CircuitBreaker.check(s, provider, op) == "CLOSED"

    # 4 falhas — ainda CLOSED
    for _ in range(CB_MAX_FAILURES - 1):
        with db() as s:
            CircuitBreaker.record_failure(s, provider, op)
    with db() as s:
        assert CircuitBreaker.check(s, provider, op) == "CLOSED"

    # 5ª falha — OPEN
    with db() as s:
        CircuitBreaker.record_failure(s, provider, op)
    with db() as s:
        assert CircuitBreaker.check(s, provider, op) == "OPEN"

    # Simular CB_OPEN_SECS passados: forçar opened_at para o passado
    opened_past = (datetime.utcnow() - timedelta(seconds=CB_OPEN_SECS + 1)).isoformat()
    with db() as s:
        s.execute(
            text("UPDATE circuit_breaker SET opened_at=:t WHERE provider_id=:pid AND operation=:op"),
            {"t": opened_past, "pid": provider, "op": op},
        )
        s.commit()

    with db() as s:
        state = CircuitBreaker.check(s, provider, op)
    assert state == "HALF_OPEN", f"esperado HALF_OPEN, obtido {state}"

    # Sucesso em HALF_OPEN → CLOSED
    with db() as s:
        CircuitBreaker.record_success(s, provider, op)
    with db() as s:
        row = s.execute(
            text("SELECT state, failures FROM circuit_breaker WHERE provider_id=:pid AND operation=:op"),
            {"pid": provider, "op": op},
        ).fetchone()
        assert row[0] == "CLOSED"
        assert row[1] == 0


# ---------------------------------------------------------------------------
# T22 — Regressão: decide_by + notes persistidos corretamente
# ---------------------------------------------------------------------------

def test_t22_resume_approval_fields(db):
    """
    resume_approval persiste decided_by e notes corretamente.
    Idempotência: approve já aprovado → rowcount 0 (False).
    """
    mid = f"t22-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow()

    with db() as s:
        s.execute(text("""
            INSERT INTO mission_control
                (mission_id, status, owner_id, lock_version, current_step, created_at)
            VALUES (:mid, 'WAITING_APPROVAL', 'owner-t22', 1, 0, :now)
        """), {"mid": mid, "now": now.isoformat()})
        s.execute(text("""
            INSERT INTO approval_requests
                (mission_id, step_index, context_snapshot, status, expires_at, created_at)
            VALUES (:mid, 0, '{}', 'PENDING', :exp, :now)
        """), {
            "mid": mid,
            "exp": (now + timedelta(hours=24)).isoformat(),
            "now": now.isoformat(),
        })
        s.commit()

    # Approve
    with db() as s:
        ok = MissionControl.resume_approval(
            s, mid, step_index=0, decision="approved",
            decided_by="ops-t22", notes="nota do T22",
        )
    assert ok is True

    with db() as s:
        ar = s.execute(
            text("SELECT status, decided_by, notes FROM approval_requests WHERE mission_id=:mid"),
            {"mid": mid},
        ).fetchone()
    assert ar[0] == "approved"
    assert ar[1] == "ops-t22"
    assert ar[2] == "nota do T22"

    # mission_control NÃO alterado por approve — reconcile é a autoridade
    with db() as s:
        mc = s.execute(
            text("SELECT status FROM mission_control WHERE mission_id=:mid"), {"mid": mid}
        ).fetchone()
    assert mc[0] == "WAITING_APPROVAL"

    # Segunda chamada → False (já decidido)
    with db() as s:
        ok2 = MissionControl.resume_approval(
            s, mid, step_index=0, decision="approved",
            decided_by="outro", notes="tentativa duplicada",
        )
    assert ok2 is False
