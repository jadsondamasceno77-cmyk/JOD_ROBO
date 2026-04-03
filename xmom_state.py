"""
X-Mom State v1.0 — Key-value persistente via SQLite (jod_robo.db).
Interface mínima: state_set() / state_get() / state_del() / state_all()
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB = Path(__file__).resolve().parent / "jod_robo.db"


_AGENT_ID = "system"  # default namespace for global state

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    # Support both schema variants: simple (key PK) and compound (agent_id, key PK)
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS xmom_state (
                agent_id   TEXT NOT NULL DEFAULT 'system',
                key        TEXT NOT NULL,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (agent_id, key)
            )
        """)
        c.commit()
    except sqlite3.OperationalError:
        pass
    return c


def state_set(key: str, value: str) -> None:
    """Persiste key=value. Cria ou sobrescreve."""
    ts = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO xmom_state (agent_id, key, value, updated_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(agent_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (_AGENT_ID, key, str(value), ts),
        )


def state_get(key: str, default: str | None = None) -> str | None:
    """Retorna valor ou default se não existir."""
    with _conn() as c:
        row = c.execute("SELECT value FROM xmom_state WHERE agent_id=? AND key=?",
                        (_AGENT_ID, key)).fetchone()
    return row[0] if row else default


def state_del(key: str) -> None:
    """Remove chave (silencioso se não existir)."""
    with _conn() as c:
        c.execute("DELETE FROM xmom_state WHERE agent_id=? AND key=?", (_AGENT_ID, key))


def state_all() -> dict[str, str]:
    """Retorna todas as chaves como dict."""
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM xmom_state WHERE agent_id=?",
                         (_AGENT_ID,)).fetchall()
    return {r[0]: r[1] for r in rows}
