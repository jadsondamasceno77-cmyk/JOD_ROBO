"""Migration das tabelas de memory_service."""
from sqlalchemy import text


def _migrate_memory_service(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS episodic_events (
                id          TEXT PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                summary     TEXT NOT NULL,
                payload     TEXT,
                occurred_at TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS semantic_facts (
                id         TEXT PRIMARY KEY,
                category   TEXT NOT NULL,
                key        TEXT NOT NULL,
                value      TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source     TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(category, key)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS procedural_patterns (
                id                 TEXT PRIMARY KEY,
                name               TEXT NOT NULL UNIQUE,
                description        TEXT NOT NULL,
                trigger_conditions TEXT,
                steps              TEXT NOT NULL,
                success_rate       REAL    DEFAULT 0.0,
                usage_count        INTEGER DEFAULT 0,
                updated_at         TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id         TEXT PRIMARY KEY,
                node_type  TEXT NOT NULL,
                label      TEXT NOT NULL,
                properties TEXT,
                created_at TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                id         TEXT PRIMARY KEY,
                source_id  TEXT NOT NULL,
                relation   TEXT NOT NULL,
                target_id  TEXT NOT NULL,
                weight     REAL DEFAULT 1.0,
                properties TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(source_id, relation, target_id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS metrics (
                id         TEXT PRIMARY KEY,
                source     TEXT NOT NULL,
                operation  TEXT NOT NULL,
                status     TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                model      TEXT,
                detail     TEXT,
                created_at TEXT NOT NULL
            )
        """))
