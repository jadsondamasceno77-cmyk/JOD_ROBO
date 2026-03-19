"""Loop de aprendizado — registro e consulta de outcomes de missão."""
from __future__ import annotations

from memory_service.storage import insert_episodic_event, list_episodic_events


def record_mission_outcome(
    session_factory,
    mission_id: str,
    status: str,
    steps_count: int,
    failed_step: str | None = None,
    error: str | None = None,
) -> None:
    payload: dict = {"mission_id": mission_id, "status": status, "steps_count": steps_count}
    if failed_step:
        payload["failed_step"] = failed_step
    if error:
        payload["error"] = error
    insert_episodic_event(
        session_factory,
        agent_id="system",
        event_type="mission_outcome",
        summary=f"mission {mission_id} {status}",
        payload=payload,
    )


def get_similar_failures(
    session_factory,
    action: str,
    limit: int = 3,
) -> list[dict]:
    rows = list_episodic_events(
        session_factory,
        event_type="mission_outcome",
        limit=100,
    )
    results = []
    for row in rows:
        p = row.get("payload") or {}
        if p.get("status") == "failed" and p.get("failed_step") and action in p["failed_step"]:
            results.append(row)
            if len(results) >= limit:
                break
    return results
