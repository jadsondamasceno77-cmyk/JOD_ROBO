"""
tests/test_watchdog.py — MACROBLOCO D

T48–T54: unitários — DB em memória, sem servidor
T55–T56: integração — servidor obrigatório em 127.0.0.1:37777
"""
import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from robo_mae.mission_control import MissionControl
from robo_mae.watchdog import WatchdogResult, WatchdogScanner

BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
DB_PATH  = "/home/wsl/JOD_ROBO/jod_robo.db"


# ---------------------------------------------------------------------------
# Fixture: DB em memória (T48–T54)
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
                next_retry_at     TEXT,
                context_json      TEXT
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
        conn.commit()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    _create_tables(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield Session
    engine.dispose()


def _stale_ts() -> str:
    return (datetime.utcnow() - timedelta(seconds=120)).isoformat()


def _future_ts(secs: int = 3600) -> str:
    return (datetime.utcnow() + timedelta(seconds=secs)).isoformat()


def _insert_mission(
    session_factory,
    mission_id: str,
    status: str,
    heartbeat_at: str = None,
    io_committed: int = None,
    last_log_status: str = None,
    retry_count: int = 0,
    max_retries: int = 3,
    step_index: int = 0,
) -> None:
    with session_factory() as s:
        s.execute(text("""
            INSERT INTO mission_control
                (mission_id, status, lock_version, owner_id, heartbeat_at,
                 retry_count, max_retries, current_step, created_at)
            VALUES (:mid, :status, 1, 'old-owner', :hb, :rc, :mr, :step, datetime('now'))
        """), {
            "mid": mission_id, "status": status, "hb": heartbeat_at,
            "rc": retry_count, "mr": max_retries, "step": step_index,
        })
        if last_log_status is not None:
            s.execute(text("""
                INSERT INTO mission_log
                    (mission_id, status, io_committed, step_index,
                     finalizer_id, action)
                VALUES (:mid, :status, :ic, :idx, 'test-fin', 'write_file')
            """), {
                "mid": mission_id, "status": last_log_status,
                "ic": io_committed, "idx": step_index,
            })
        s.commit()


def _insert_approval(
    session_factory,
    mission_id: str,
    step_index: int,
    ar_status: str,
    expires_at: str,
) -> None:
    now = datetime.utcnow().isoformat()
    with session_factory() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO approval_requests
                (mission_id, step_index, context_snapshot, status, expires_at, created_at)
            VALUES (:mid, :idx, '{}', :status, :exp, :now)
        """), {
            "mid": mission_id, "idx": step_index,
            "status": ar_status, "exp": expires_at, "now": now,
        })
        s.commit()


# ---------------------------------------------------------------------------
# T48 — RUNNING + stale + estado ambíguo → QUARANTINED
# ---------------------------------------------------------------------------

def test_t48_running_stale_ambiguous_quarantined(db):
    """RUNNING + stale + último step RUNNING sem io_committed → QUARANTINE."""
    mid = str(uuid.uuid4())
    _insert_mission(db, mid, "RUNNING",
                    heartbeat_at=_stale_ts(),
                    last_log_status="RUNNING",
                    io_committed=None)

    called = []

    async def fake_redispatch(mission_id):
        called.append(mission_id)

    scanner = WatchdogScanner(db, fake_redispatch)
    result = asyncio.run(scanner.scan_once())

    assert result.scanned == 1
    assert result.quarantined == 1
    assert result.resumed == 0

    with db() as s:
        row = s.execute(
            text("SELECT status FROM mission_control WHERE mission_id=:mid"),
            {"mid": mid},
        ).fetchone()
    assert row[0] == "QUARANTINED"


# ---------------------------------------------------------------------------
# T49 — RUNNING + stale + retries esgotados → FAILED
# ---------------------------------------------------------------------------

def test_t49_running_stale_retries_exhausted_failed(db):
    """RUNNING + stale + retry_count >= max_retries → FAILED."""
    mid = str(uuid.uuid4())
    _insert_mission(db, mid, "RUNNING",
                    heartbeat_at=_stale_ts(),
                    last_log_status="error",
                    retry_count=3, max_retries=3)

    called = []

    async def fake_redispatch(mission_id):
        called.append(mission_id)

    scanner = WatchdogScanner(db, fake_redispatch)
    result = asyncio.run(scanner.scan_once())

    assert result.scanned == 1
    assert result.failed == 1
    assert result.resumed == 0
    assert result.quarantined == 0

    with db() as s:
        row = s.execute(
            text("SELECT status FROM mission_control WHERE mission_id=:mid"),
            {"mid": mid},
        ).fetchone()
    assert row[0] == "FAILED"


# ---------------------------------------------------------------------------
# T50 — RUNNING + heartbeat fresco → NOOP
# ---------------------------------------------------------------------------

def test_t50_running_fresh_heartbeat_noop(db):
    """RUNNING + heartbeat fresco → NOOP, sem alterar mission_control."""
    mid = str(uuid.uuid4())
    fresh_ts = datetime.utcnow().isoformat()
    _insert_mission(db, mid, "RUNNING", heartbeat_at=fresh_ts)

    called = []

    async def fake_redispatch(mission_id):
        called.append(mission_id)

    scanner = WatchdogScanner(db, fake_redispatch)
    result = asyncio.run(scanner.scan_once())

    assert result.scanned == 1
    assert result.noop == 1
    assert result.resumed == 0
    assert result.quarantined == 0
    assert result.failed == 0


# ---------------------------------------------------------------------------
# T51 — WAITING_APPROVAL + approved → RESUME + redespacho contabilizado
# ---------------------------------------------------------------------------

def test_t51_waiting_approval_approved_resume(db):
    """WAITING_APPROVAL + approval_request approved → RESUME, resumed += 1."""
    mid = str(uuid.uuid4())
    _insert_mission(db, mid, "WAITING_APPROVAL", heartbeat_at=None, step_index=0)
    _insert_approval(db, mid, step_index=0, ar_status="approved",
                     expires_at=_future_ts())

    called = []

    async def fake_redispatch(mission_id):
        called.append(mission_id)

    scanner = WatchdogScanner(db, fake_redispatch)
    result = asyncio.run(scanner.scan_once())

    assert result.scanned == 1
    assert result.resumed == 1
    assert result.failed == 0
    assert result.quarantined == 0


# ---------------------------------------------------------------------------
# T52 — WAITING_APPROVAL + expired → FAILED
# ---------------------------------------------------------------------------

def test_t52_waiting_approval_expired_failed(db):
    """WAITING_APPROVAL + approval_request PENDING expirado → FAIL."""
    mid = str(uuid.uuid4())
    _insert_mission(db, mid, "WAITING_APPROVAL", heartbeat_at=None, step_index=0)
    # expires_at no passado, status PENDING
    _insert_approval(db, mid, step_index=0, ar_status="PENDING",
                     expires_at=_stale_ts())

    called = []

    async def fake_redispatch(mission_id):
        called.append(mission_id)

    scanner = WatchdogScanner(db, fake_redispatch)
    result = asyncio.run(scanner.scan_once())

    assert result.scanned == 1
    assert result.failed == 1
    assert result.resumed == 0

    with db() as s:
        row = s.execute(
            text("SELECT status FROM mission_control WHERE mission_id=:mid"),
            {"mid": mid},
        ).fetchone()
    assert row[0] == "FAILED"


# ---------------------------------------------------------------------------
# T53 — claim atômico sequencial → apenas 1 winner
# ---------------------------------------------------------------------------

def test_t53_claim_atomic_sequential(db):
    """Dois claims sequenciais no mesmo PENDING → só o primeiro vence."""
    mid = str(uuid.uuid4())
    with db() as s:
        MissionControl.create(s, mid)

    owner_a = str(uuid.uuid4())
    owner_b = str(uuid.uuid4())

    with db() as s:
        ver_a = MissionControl.claim(s, mid, owner_a)
    with db() as s:
        ver_b = MissionControl.claim(s, mid, owner_b)

    assert ver_a == 1, "primeiro claim deve vencer"
    assert ver_b is None, "segundo claim deve falhar (já RUNNING)"


# ---------------------------------------------------------------------------
# T54 — takeover concorrente → apenas 1 winner
# ---------------------------------------------------------------------------

def test_t54_takeover_concurrent_single_winner(db):
    """Dois takeovers em missão RUNNING+stale → apenas o primeiro vence."""
    mid = str(uuid.uuid4())
    _insert_mission(db, mid, "RUNNING", heartbeat_at=_stale_ts())

    owner_a = str(uuid.uuid4())
    owner_b = str(uuid.uuid4())

    with db() as s:
        ver_a = MissionControl.takeover(s, mid, owner_a)
    with db() as s:
        ver_b = MissionControl.takeover(s, mid, owner_b)

    assert ver_a is not None, "primeiro takeover deve vencer"
    assert ver_b is None, "segundo takeover deve falhar (lock_version já avançou)"


# ---------------------------------------------------------------------------
# T55 — POST /watchdog/scan retorna 200 e campos completos
# ---------------------------------------------------------------------------

def test_t55_endpoint_returns_200_and_fields():
    """POST /watchdog/scan retorna 200 com todos os campos esperados."""
    r = httpx.post(f"{BASE_URL}/watchdog/scan", headers=HEADERS, timeout=10.0)
    assert r.status_code == 200, f"esperado 200, got {r.status_code}: {r.text}"
    body = r.json()
    for field in ("scanned", "resumed", "quarantined", "failed", "noop"):
        assert field in body, f"campo ausente: {field}"
        assert isinstance(body[field], int), f"campo {field} deve ser int"


# ---------------------------------------------------------------------------
# T56 — integração real: RUNNING+stale → watchdog redespacha
# ---------------------------------------------------------------------------

def test_t56_integration_running_stale_redispatched():
    """
    Injeta missão RUNNING+stale com context_json no DB real.
    Chama /watchdog/scan e verifica que a missão foi processada pelo watchdog
    (resumed >= 1 — ownership/fencing preservados pelo caminho normal).
    """
    mid = f"t56-{uuid.uuid4().hex[:8]}"
    stale_ts = (datetime.utcnow() - timedelta(seconds=120)).isoformat()
    ctx_json = json.dumps({
        "finalizer_id":     "nonexistent-fin-t56",
        "guardian_id":      None,
        "steps":            [
            {"action": "write_file", "target_path": f"tests/{mid}.txt",
             "payload": "watchdog-test", "mode": "apply"},
        ],
        "max_retries":       0,
        "retry_delay_secs":  2.0,
        "approval_ttl_secs": 86400,
    })

    # Injetar missão RUNNING+stale com último log 'applied' → reconcile → RESUME
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("""
            INSERT OR IGNORE INTO mission_control
                (mission_id, status, lock_version, owner_id, heartbeat_at,
                 created_at, max_retries, retry_count, context_json)
            VALUES (?, 'RUNNING', 1, 'old-owner-t56', ?, datetime('now'), 0, 0, ?)
        """, (mid, stale_ts, ctx_json))
        con.execute("""
            INSERT INTO mission_log
                (mission_id, status, io_committed, step_index, finalizer_id, action)
            VALUES (?, 'applied', 1, 0, 'nonexistent-fin-t56', 'write_file')
        """, (mid,))
        con.commit()
    finally:
        con.close()

    try:
        r = httpx.post(f"{BASE_URL}/watchdog/scan", headers=HEADERS, timeout=15.0)
        assert r.status_code == 200, f"esperado 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["scanned"] >= 1
        # reconcile vê RUNNING+stale+applied → RESUME → redispatch_fn acionada
        assert body["resumed"] >= 1, (
            f"esperado resumed >= 1, got: {body}"
        )
    finally:
        # Cleanup: remover missão de teste do DB real
        con = sqlite3.connect(DB_PATH)
        try:
            con.execute("DELETE FROM mission_control WHERE mission_id=?", (mid,))
            con.execute("DELETE FROM mission_log WHERE mission_id=?", (mid,))
            con.commit()
        finally:
            con.close()
