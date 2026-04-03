"""
X-Mom Semantic Memory v1.0 — pipeline que alimenta semantic_memory após cada output.
Usa keyword-overlap como heurística de similaridade (sem embeddings externos).
"""
from __future__ import annotations
import sqlite3, json, re
from datetime import datetime, timezone
from pathlib import Path

_DB = Path(__file__).resolve().parent / "jod_robo.db"

_STOP_PT = {
    "para","como","mais","isso","esse","esta","aqui","com","por","mas","uma",
    "que","não","dos","das","são","ser","ter","nos","nas","pelo","pela","entre",
    "sobre","sem","seu","sua","seus","suas","este","esta","eles","elas","você",
    "isso","aqui","ali","quando","onde","quem","qual","quais","cada","todos",
}

def _keywords(text: str, top_n: int = 25) -> list[str]:
    """Extrai top-N palavras-chave por frequência, sem stopwords."""
    words = re.findall(r'\b[a-záàãâéêíóôõúüçA-ZÁÀÃÂÉÊÍÓÔÕÚÜÇ]{4,}\b', text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOP_PT:
            freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=freq.get, reverse=True)[:top_n]  # type: ignore[arg-type]


def feed_semantic_memory(
    session_id: str,
    squad: str,
    content: str,
    score: float = 7.0,
) -> int:
    """Insere output gerado na semantic_memory. Retorna rowid inserido."""
    kw  = json.dumps(_keywords(content), ensure_ascii=False)
    ts  = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(_DB)
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO semantic_memory (session_id, squad, content, score, created_at, embedding) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, squad, content[:2000], score, ts, kw),
    )
    rowid = cur.lastrowid
    conn.commit()
    conn.close()
    return rowid or 0


def search_semantic(query: str, limit: int = 5, min_score: float = 0.0) -> list[dict]:
    """Busca entradas relevantes por overlap de keywords. Retorna lista ordenada por relevância."""
    q_kw = set(_keywords(query, top_n=15))
    if not q_kw:
        return []
    conn = sqlite3.connect(_DB)
    rows = conn.execute(
        "SELECT session_id, squad, content, score, created_at, embedding "
        "FROM semantic_memory WHERE score >= ? ORDER BY created_at DESC LIMIT 200",
        (min_score,),
    ).fetchall()
    conn.close()

    results: list[dict] = []
    for r in rows:
        try:
            entry_kw = set(json.loads(r[5] or "[]"))
        except Exception:
            entry_kw = set()
        overlap = len(q_kw & entry_kw)
        if overlap > 0:
            results.append({
                "session_id": r[0],
                "squad":      r[1],
                "content":    r[2][:400],
                "score":      r[3],
                "created_at": r[4],
                "relevance":  overlap,
            })

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:limit]


def semantic_context_for(query: str) -> str:
    """Retorna contexto semântico formatado para injetar no prompt."""
    hits = search_semantic(query, limit=3, min_score=7.0)
    if not hits:
        return ""
    parts = [f"[Memória {i+1} — {h['squad']} / score {h['score']}]\n{h['content']}"
             for i, h in enumerate(hits)]
    return "\n\n".join(parts)
