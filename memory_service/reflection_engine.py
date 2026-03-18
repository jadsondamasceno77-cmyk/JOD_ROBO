"""
Reflection Engine — consolida aprendizado fora do caminho crítico.

Roda FORA do caminho crítico:
- não acessa mission_control, mission_log, approval_requests, circuit_breaker
- não governa commit, veto, reconcile, approval, retry, quarantine ou fencing
- toda saída é advisory_only via policy_guard.enforce_advisory()
- usage_count não é alterado — rastreado pelo executor, não pela reflexão

Operações:
  consolidate_signals()   — conta eventos por tipo → semantic_facts (reflection_signal)
  update_pattern_score()  — ajusta success_rate + updated_at (NÃO toca usage_count)
  run_reflection()        — rodada completa: consolida + promove/rebaixa patterns
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import text

from .policy_guard import enforce_advisory, wrap_advisory
from .storage import upsert_semantic_fact, list_procedural_patterns


_POSITIVE_TYPES = frozenset({"applied", "success", "task_done", "step"})
_NEGATIVE_TYPES = frozenset({"error", "failed", "vetoed", "io_failed"})


def _count_events_by_type(
    session_factory, agent_id: str | None = None
) -> dict[str, int]:
    params: dict = {}
    where = ""
    if agent_id:
        where = "WHERE agent_id = :agent_id"
        params["agent_id"] = agent_id
    with session_factory() as s:
        rows = s.execute(text(f"""
            SELECT event_type, COUNT(*) FROM episodic_events {where}
            GROUP BY event_type
        """), params).fetchall()
    return {r[0]: r[1] for r in rows}


def consolidate_signals(
    session_factory, agent_id: str | None = None
) -> dict[str, int]:
    """
    Agrega contagens de eventos por tipo → upserta semantic_facts.
    category='reflection_signal', key='<event_type>_<scope>'.
    Grava também 'last_reflection_<scope>' em category='reflection_meta'.
    """
    scope = agent_id or "global"
    counts = _count_events_by_type(session_factory, agent_id=agent_id)
    for event_type, count in counts.items():
        upsert_semantic_fact(
            session_factory,
            category="reflection_signal",
            key=f"{event_type}_{scope}",
            value=str(count),
            source="reflection_engine",
        )
    upsert_semantic_fact(
        session_factory,
        category="reflection_meta",
        key=f"last_reflection_{scope}",
        value=datetime.utcnow().isoformat(),
        source="reflection_engine",
    )
    return counts


def update_pattern_score(
    session_factory, name: str, delta: float
) -> float | None:
    """
    Ajusta success_rate por delta (clamp [0.0, 1.0]).
    Atualiza updated_at.
    NÃO altera usage_count — uso real é rastreado pelo executor, não pela reflexão.
    Retorna novo success_rate, ou None se o pattern não existe.
    """
    with session_factory() as s:
        row = s.execute(
            text("SELECT success_rate FROM procedural_patterns WHERE name = :name"),
            {"name": name},
        ).fetchone()
        if not row:
            return None
        new_rate = max(0.0, min(1.0, row[0] + delta))
        s.execute(text("""
            UPDATE procedural_patterns
            SET success_rate = :rate, updated_at = :ts
            WHERE name = :name
        """), {
            "rate": new_rate,
            "ts":   datetime.utcnow().isoformat(),
            "name": name,
        })
        s.commit()
    return new_rate


def _adjust_patterns(
    session_factory,
    counts: dict[str, int],
    agent_id: str | None = None,
) -> list[dict]:
    """
    Para cada pattern, conta eventos positivos/negativos que mencionam o nome
    do pattern no summary (LIKE).

    Escopo:
    - agent_id fornecido → avalia apenas eventos desse agente
    - agent_id=None     → reflexão global (todos os eventos)

    Calcula target_rate e aplica ajuste incremental suavizado (20% do gap por rodada).
    Não toca usage_count.
    """
    total_positive = sum(v for k, v in counts.items() if k in _POSITIVE_TYPES)
    total_negative = sum(v for k, v in counts.items() if k in _NEGATIVE_TYPES)
    if total_positive + total_negative == 0:
        return []

    scope_filter = "AND agent_id = :agent_id" if agent_id else ""
    patterns = list_procedural_patterns(session_factory)
    changes = []

    for pat in patterns:
        params_base: dict = {"pat": f"%{pat['name']}%"}
        if agent_id:
            params_base["agent_id"] = agent_id

        with session_factory() as s:
            pos = s.execute(text(f"""
                SELECT COUNT(*) FROM episodic_events
                WHERE summary LIKE :pat {scope_filter}
                  AND event_type IN ('applied','success','task_done','step')
            """), params_base).fetchone()[0]
            neg = s.execute(text(f"""
                SELECT COUNT(*) FROM episodic_events
                WHERE summary LIKE :pat {scope_filter}
                  AND event_type IN ('error','failed','vetoed','io_failed')
            """), params_base).fetchone()[0]

        if pos + neg == 0:
            continue
        target_rate = pos / (pos + neg)
        delta = (target_rate - pat["success_rate"]) * 0.2
        if abs(delta) < 0.01:
            continue
        new_rate = update_pattern_score(session_factory, pat["name"], delta)
        changes.append({
            "name":     pat["name"],
            "old_rate": round(pat["success_rate"], 4),
            "new_rate": round(new_rate, 4),
        })
    return changes


def run_reflection(
    session_factory, agent_id: str | None = None
) -> dict:
    """
    Rodada completa de reflexão:
    1. Consolida sinais episódicos → semantic_facts
    2. Promove/rebaixa patterns com base em evidência (escopada por agent_id)
    3. Retorna relatório advisory_only

    run_reflection(agent_id=X)    → usa apenas eventos de X
    run_reflection(agent_id=None) → reflexão global
    """
    counts          = consolidate_signals(session_factory, agent_id=agent_id)
    pattern_changes = _adjust_patterns(session_factory, counts, agent_id=agent_id)
    report = {
        "scope":                 agent_id or "global",
        "signal_counts":         counts,
        "total_events_analyzed": sum(counts.values()),
        "patterns_adjusted":     len(pattern_changes),
        "pattern_changes":       pattern_changes,
    }
    return enforce_advisory(wrap_advisory(report))
