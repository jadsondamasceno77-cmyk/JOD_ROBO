"""CRUD de baixo nível para as tabelas de memory_service."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from sqlalchemy import text


def _now() -> str:
    return datetime.utcnow().isoformat()


# ── Episodic Events ───────────────────────────────────────────────────────────

def insert_episodic_event(
    session_factory,
    agent_id: str,
    event_type: str,
    summary: str,
    payload: dict | None = None,
    occurred_at: str | None = None,
) -> str:
    eid, now = str(uuid.uuid4()), _now()
    with session_factory() as s:
        s.execute(text("""
            INSERT INTO episodic_events
                (id, agent_id, event_type, summary, payload, occurred_at, created_at)
            VALUES
                (:id, :agent_id, :event_type, :summary, :payload, :occurred_at, :created_at)
        """), {
            "id": eid, "agent_id": agent_id, "event_type": event_type,
            "summary": summary,
            "payload": json.dumps(payload) if payload else None,
            "occurred_at": occurred_at or now, "created_at": now,
        })
        s.commit()
    return eid


def list_episodic_events(
    session_factory,
    agent_id: str | None = None,
    event_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    filters, params = [], {"limit": limit}
    if agent_id:
        filters.append("agent_id = :agent_id")
        params["agent_id"] = agent_id
    if event_type:
        filters.append("event_type = :event_type")
        params["event_type"] = event_type
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    with session_factory() as s:
        rows = s.execute(text(f"""
            SELECT id, agent_id, event_type, summary, payload, occurred_at, created_at
            FROM episodic_events {where}
            ORDER BY occurred_at DESC LIMIT :limit
        """), params).fetchall()
    return [
        {
            "id": r[0], "agent_id": r[1], "event_type": r[2], "summary": r[3],
            "payload": json.loads(r[4]) if r[4] else None,
            "occurred_at": r[5], "created_at": r[6],
        }
        for r in rows
    ]


# ── Semantic Facts ────────────────────────────────────────────────────────────

def upsert_semantic_fact(
    session_factory,
    category: str,
    key: str,
    value: str,
    confidence: float = 1.0,
    source: str | None = None,
) -> str:
    fid, now = str(uuid.uuid4()), _now()
    with session_factory() as s:
        s.execute(text("""
            INSERT INTO semantic_facts
                (id, category, key, value, confidence, source, updated_at)
            VALUES
                (:id, :category, :key, :value, :confidence, :source, :updated_at)
            ON CONFLICT(category, key) DO UPDATE SET
                value      = excluded.value,
                confidence = excluded.confidence,
                source     = excluded.source,
                updated_at = excluded.updated_at
        """), {
            "id": fid, "category": category, "key": key,
            "value": value, "confidence": confidence,
            "source": source, "updated_at": now,
        })
        s.commit()
    return fid


def list_semantic_facts(
    session_factory,
    category: str | None = None,
    key: str | None = None,
) -> list[dict]:
    filters, params = [], {}
    if category:
        filters.append("category = :category")
        params["category"] = category
    if key:
        filters.append("key = :key")
        params["key"] = key
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    with session_factory() as s:
        rows = s.execute(text(f"""
            SELECT id, category, key, value, confidence, source, updated_at
            FROM semantic_facts {where}
            ORDER BY category, key
        """), params).fetchall()
    return [
        {
            "id": r[0], "category": r[1], "key": r[2], "value": r[3],
            "confidence": r[4], "source": r[5], "updated_at": r[6],
        }
        for r in rows
    ]


# ── Procedural Patterns ───────────────────────────────────────────────────────

def upsert_procedural_pattern(
    session_factory,
    name: str,
    description: str,
    steps: list,
    trigger_conditions: list | None = None,
    success_rate: float = 0.0,
) -> str:
    pid, now = str(uuid.uuid4()), _now()
    with session_factory() as s:
        s.execute(text("""
            INSERT INTO procedural_patterns
                (id, name, description, trigger_conditions, steps,
                 success_rate, usage_count, updated_at)
            VALUES
                (:id, :name, :description, :tc, :steps, :sr, 0, :updated_at)
            ON CONFLICT(name) DO UPDATE SET
                description        = excluded.description,
                trigger_conditions = excluded.trigger_conditions,
                steps              = excluded.steps,
                success_rate       = excluded.success_rate,
                updated_at         = excluded.updated_at
        """), {
            "id": pid, "name": name, "description": description,
            "tc": json.dumps(trigger_conditions) if trigger_conditions else None,
            "steps": json.dumps(steps), "sr": success_rate, "updated_at": now,
        })
        s.commit()
    return pid


def list_procedural_patterns(
    session_factory,
    name: str | None = None,
) -> list[dict]:
    filters, params = [], {}
    if name:
        filters.append("name = :name")
        params["name"] = name
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    with session_factory() as s:
        rows = s.execute(text(f"""
            SELECT id, name, description, trigger_conditions, steps,
                   success_rate, usage_count, updated_at
            FROM procedural_patterns {where}
            ORDER BY name
        """), params).fetchall()
    return [
        {
            "id": r[0], "name": r[1], "description": r[2],
            "trigger_conditions": json.loads(r[3]) if r[3] else None,
            "steps": json.loads(r[4]),
            "success_rate": r[5], "usage_count": r[6], "updated_at": r[7],
        }
        for r in rows
    ]


# ── Graph Nodes ───────────────────────────────────────────────────────────────

def insert_graph_node(
    session_factory,
    node_type: str,
    label: str,
    properties: dict | None = None,
) -> str:
    nid, now = str(uuid.uuid4()), _now()
    with session_factory() as s:
        s.execute(text("""
            INSERT INTO graph_nodes (id, node_type, label, properties, created_at)
            VALUES (:id, :node_type, :label, :properties, :created_at)
        """), {
            "id": nid, "node_type": node_type, "label": label,
            "properties": json.dumps(properties) if properties else None,
            "created_at": now,
        })
        s.commit()
    return nid


def find_node_by_label(session_factory, label: str) -> str | None:
    """Retorna node_id do primeiro nó com o label dado, ou None."""
    with session_factory() as s:
        row = s.execute(
            text("SELECT id FROM graph_nodes WHERE label = :label LIMIT 1"),
            {"label": label},
        ).fetchone()
    return row[0] if row else None


def list_graph_nodes(
    session_factory,
    node_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    filters, params = [], {"limit": limit}
    if node_type:
        filters.append("node_type = :node_type")
        params["node_type"] = node_type
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    with session_factory() as s:
        rows = s.execute(text(f"""
            SELECT id, node_type, label, properties, created_at
            FROM graph_nodes {where}
            ORDER BY created_at DESC LIMIT :limit
        """), params).fetchall()
    return [
        {
            "id": r[0], "node_type": r[1], "label": r[2],
            "properties": json.loads(r[3]) if r[3] else None,
            "created_at": r[4],
        }
        for r in rows
    ]


# ── Graph Edges ───────────────────────────────────────────────────────────────

def insert_graph_edge(
    session_factory,
    source_id: str,
    relation: str,
    target_id: str,
    weight: float = 1.0,
    properties: dict | None = None,
) -> str:
    eid, now = str(uuid.uuid4()), _now()
    with session_factory() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO graph_edges
                (id, source_id, relation, target_id, weight, properties, created_at)
            VALUES
                (:id, :source_id, :relation, :target_id, :weight, :properties, :created_at)
        """), {
            "id": eid, "source_id": source_id, "relation": relation,
            "target_id": target_id, "weight": weight,
            "properties": json.dumps(properties) if properties else None,
            "created_at": now,
        })
        s.commit()
    return eid


def list_graph_neighbors(
    session_factory,
    node_id: str,
    relation: str | None = None,
) -> list[dict]:
    params: dict = {"node_id": node_id}
    rel_filter = ""
    if relation:
        rel_filter = "AND e.relation = :relation"
        params["relation"] = relation
    with session_factory() as s:
        rows = s.execute(text(f"""
            SELECT e.id, e.source_id, e.relation, e.target_id, e.weight,
                   n.node_type, n.label
            FROM graph_edges e
            JOIN graph_nodes n ON n.id = e.target_id
            WHERE e.source_id = :node_id {rel_filter}
            ORDER BY e.relation, n.label
        """), params).fetchall()
    return [
        {
            "edge_id": r[0], "source_id": r[1], "relation": r[2],
            "target_id": r[3], "weight": r[4],
            "target_type": r[5], "target_label": r[6],
        }
        for r in rows
    ]


# ── Reflection Signals ────────────────────────────────────────────────────────

def list_reflection_signals(
    session_factory, scope: str | None = None, limit: int = 5
) -> list[dict]:
    """
    Retorna top sinais de reflexão (category=reflection_signal), ordenados por contagem DESC.

    scope fornecido → match exato de sufixo '_<scope>' via substr/length.
    Não usa LIKE com underscore porque '_' é wildcard no SQLite.

    scope=None → retorna todos os sinais globais e escopados.
    """
    params: dict = {"limit": limit}
    scope_filter = ""
    if scope:
        # Exact suffix match: last len(scope) chars == scope AND char before == '_'
        scope_filter = """
            AND length(key) > length(:scope)
            AND substr(key, length(key) - length(:scope) + 1) = :scope
            AND substr(key, length(key) - length(:scope), 1) = '_'
        """
        params["scope"] = scope
    with session_factory() as s:
        rows = s.execute(text(f"""
            SELECT key, value FROM semantic_facts
            WHERE category = 'reflection_signal'
            {scope_filter}
            ORDER BY CAST(value AS INTEGER) DESC LIMIT :limit
        """), params).fetchall()
    return [{"signal": r[0], "count": int(r[1])} for r in rows]
