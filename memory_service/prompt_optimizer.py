"""Auto-otimização de prompts via contagem de falhas de parse JSON."""
from __future__ import annotations

from memory_service.storage import upsert_semantic_fact, list_semantic_facts, insert_episodic_event

_REINFORCED_PREFIX = (
    "CRÍTICO: Responda APENAS com JSON válido. "
    "Sem texto antes ou depois. Sem markdown. Apenas o objeto JSON."
)


def record_json_failure(session_factory, schema_name: str, prompt_snippet: str) -> None:
    current = get_failure_count(session_factory, schema_name)
    upsert_semantic_fact(
        session_factory,
        category="prompt_failure",
        key=schema_name,
        value=str(current + 1),
        source="prompt_optimizer",
    )
    insert_episodic_event(
        session_factory,
        agent_id="system",
        event_type="json_parse_failure",
        summary=f"JSON parse failure for schema {schema_name}",
        payload={"schema_name": schema_name, "prompt_snippet": prompt_snippet[:200]},
    )


def get_failure_count(session_factory, schema_name: str) -> int:
    rows = list_semantic_facts(session_factory, category="prompt_failure", key=schema_name)
    if not rows:
        return 0
    try:
        return int(rows[0]["value"])
    except (ValueError, KeyError):
        return 0


def get_optimized_prefix(session_factory, schema_name: str) -> str:
    if get_failure_count(session_factory, schema_name) >= 2:
        return _REINFORCED_PREFIX
    return ""
