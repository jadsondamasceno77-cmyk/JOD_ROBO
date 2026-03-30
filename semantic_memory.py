#!/usr/bin/env python3
import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent / "jod_robo.db"
_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def save_semantic(session_id, squad, content, score=7.0):
    try:
        emb = _get_model().encode(content[:500]).tolist()
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO semantic_memory (session_id,squad,content,embedding,score,created_at) VALUES (?,?,?,?,?,?)",
            (session_id, squad, content[:1000], json.dumps(emb), score,
             datetime.now(timezone.utc).isoformat()))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[semantic_memory] save erro: {e}")

def search_semantic(query, limit=3):
    try:
        import numpy as np
        q = np.array(_get_model().encode(query))
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT session_id,squad,content,embedding,score FROM semantic_memory ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        conn.close()
        results = []
        for row in rows:
            try:
                emb = np.array(json.loads(row[3]))
                sim = float(np.dot(q,emb)/(np.linalg.norm(q)*np.linalg.norm(emb)+1e-10))
                if sim > 0.3:
                    results.append({"session":row[0],"squad":row[1],"content":row[2],"similarity":sim,"score":row[4]})
            except: pass
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
    except Exception as e:
        return []

def get_context(query):
    results = search_semantic(query, limit=3)
    if not results: return ""
    return "CONTEXTO RELEVANTE:\n" + "\n".join([f"[{r['squad']}] {r['content'][:200]}" for r in results])
