"""
X-Mom Bus v2.0 — Roteador local + Task Queue (pub/sub via xmom_events).
Zero chamadas LLM para routing. Suporte a orquestração multi-agente.
"""
from __future__ import annotations
import sqlite3, json, time
from pathlib import Path

_DB = Path(__file__).resolve().parent / "jod_robo.db"

# Squad extra: social-squad (não está no SQUADS original)
SOCIAL_SQUAD: dict = {
    "social-squad": {
        "chief": "social-chief",
        "keywords": [
            "instagram", "post", "stories", "reels", "tiktok",
            "twitter", "linkedin post", "social media", "redes sociais",
            "feed", "legenda", "caption", "hashtag", "conteudo social",
            "publicacao", "publicar", "criar post", "crie um post",
            "novo post", "post para instagram", "post instagram",
            "gere post", "gerar post", "post para redes sociais",
        ],
    }
}

# Padrões para intent create_post (avaliados antes do roteamento geral)
_CREATE_POST_PATTERNS = [
    "crie um post", "criar post", "novo post",
    "post para instagram", "post instagram",
    "crie post", "gere post", "gerar post",
    "post para redes sociais", "criar post para",
]


def route_local(message: str, squads: dict) -> tuple[str, int]:
    """Retorna (squad_slug, score) sem chamar nenhuma LLM.

    Combina SQUADS originais + SOCIAL_SQUAD.
    Desempate: prefere squads com maior score de keyword.
    Heurística de fallback: msg curta → c-level-squad, longa → advisory-board.
    """
    ml = message.lower()
    all_squads = {**squads, **SOCIAL_SQUAD}

    scores: dict[str, int] = {
        sq: sum(1 for kw in data["keywords"] if kw in ml)
        for sq, data in all_squads.items()
    }
    positive = {k: v for k, v in scores.items() if v > 0}

    if not positive:
        fallback = "c-level-squad" if len(message.split()) <= 3 else "advisory-board"
        return fallback, 0

    best = max(positive, key=positive.get)  # type: ignore[arg-type]
    return best, positive[best]


def detect_intent_local(message: str) -> dict | None:
    """Detecta intents de alto nível localmente.

    Retorna dict de intent ou None (deixa detect_intent original processar).
    """
    ml = message.lower().strip()

    for pattern in _CREATE_POST_PATTERNS:
        if pattern in ml:
            return {"intent": "create_post", "message": message}

    return None  # sinaliza "sem intent especial aqui, continua fluxo normal"


# ─── TASK QUEUE (pub/sub via xmom_events) ───────────────────────────────────────

def _ensure_events_table() -> None:
    conn = sqlite3.connect(_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xmom_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            source     TEXT,
            payload    TEXT,
            timestamp  REAL
        )
    """)
    conn.commit()
    conn.close()


def publish_task(
    task_type: str,
    payload: dict,
    source: str = "system",
) -> int:
    """Publica uma tarefa na fila. Retorna event_id."""
    _ensure_events_table()
    data = json.dumps({"status": "pending", **payload}, ensure_ascii=False)
    conn = sqlite3.connect(_DB)
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO xmom_events (event_type, source, payload, timestamp) VALUES (?,?,?,?)",
        (task_type, source, data, time.time()),
    )
    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    return event_id or 0


def consume_task(task_type: str, limit: int = 5) -> list[dict]:
    """Retorna tarefas pendentes do tipo dado e as marca como 'processing'."""
    _ensure_events_table()
    conn = sqlite3.connect(_DB)
    rows = conn.execute(
        "SELECT id, source, payload, timestamp FROM xmom_events "
        "WHERE event_type=? AND json_extract(payload,'$.status')='pending' "
        "ORDER BY timestamp ASC LIMIT ?",
        (task_type, limit),
    ).fetchall()
    tasks = []
    for row in rows:
        try:
            pl = json.loads(row[2])
        except Exception:
            pl = {}
        pl["status"] = "processing"
        conn.execute(
            "UPDATE xmom_events SET payload=? WHERE id=?",
            (json.dumps(pl, ensure_ascii=False), row[0]),
        )
        tasks.append({"id": row[0], "source": row[1], "payload": pl, "ts": row[3]})
    conn.commit()
    conn.close()
    return tasks


def complete_task(event_id: int, result: str) -> None:
    """Marca tarefa como concluída com resultado."""
    _ensure_events_table()
    conn = sqlite3.connect(_DB)
    rows = conn.execute("SELECT payload FROM xmom_events WHERE id=?", (event_id,)).fetchone()
    if rows:
        try:
            pl = json.loads(rows[0])
        except Exception:
            pl = {}
        pl.update({"status": "done", "result": result[:500]})
        conn.execute(
            "UPDATE xmom_events SET payload=? WHERE id=?",
            (json.dumps(pl, ensure_ascii=False), event_id),
        )
        conn.commit()
    conn.close()


def pending_count(task_type: str | None = None) -> int:
    """Conta tarefas pendentes."""
    _ensure_events_table()
    conn = sqlite3.connect(_DB)
    if task_type:
        n = conn.execute(
            "SELECT COUNT(*) FROM xmom_events WHERE event_type=? AND json_extract(payload,'$.status')='pending'",
            (task_type,),
        ).fetchone()[0]
    else:
        n = conn.execute(
            "SELECT COUNT(*) FROM xmom_events WHERE json_extract(payload,'$.status')='pending'"
        ).fetchone()[0]
    conn.close()
    return n
