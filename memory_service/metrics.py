"""Métricas de execução — coleta e consulta."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_metric(
    session_factory,
    source: str,
    operation: str,
    status: str,
    latency_ms: float,
    model: str | None = None,
    detail: str | None = None,
) -> str:
    mid = str(uuid.uuid4())
    with session_factory() as s:
        s.execute(text("""
            INSERT INTO metrics (id, source, operation, status, latency_ms, model, detail, created_at)
            VALUES (:id, :source, :operation, :status, :latency_ms, :model, :detail, :created_at)
        """), {
            "id": mid, "source": source, "operation": operation,
            "status": status, "latency_ms": latency_ms,
            "model": model, "detail": detail, "created_at": _now(),
        })
        s.commit()
    return mid


def query_metrics_summary(session_factory, hours: int = 24) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with session_factory() as s:
        rows = s.execute(text("""
            SELECT status, operation, model, latency_ms
            FROM metrics
            WHERE created_at >= :since
            ORDER BY latency_ms
        """), {"since": since}).fetchall()

    total = len(rows)
    by_status: dict[str, int] = {}
    by_model: dict[str, int] = {}
    by_operation: dict[str, int] = {}
    latencies: list[float] = []

    for status, operation, model, latency_ms in rows:
        by_status[status] = by_status.get(status, 0) + 1
        by_operation[operation] = by_operation.get(operation, 0) + 1
        if model:
            by_model[model] = by_model.get(model, 0) + 1
        latencies.append(latency_ms)

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

    return {
        "hours": hours,
        "total": total,
        "by_status": by_status,
        "by_operation": by_operation,
        "by_model": by_model,
        "latency_avg_ms": round(avg_latency, 2),
        "latency_p95_ms": round(p95_latency, 2),
    }
