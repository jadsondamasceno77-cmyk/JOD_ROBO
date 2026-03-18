from sqlalchemy import text


def get_mission_summary(session_factory, mission_id: str) -> dict:
    with session_factory() as s:
        rows = s.execute(
            text("SELECT * FROM mission_log WHERE mission_id = :mid ORDER BY id"),
            {"mid": mission_id},
        ).fetchall()
        step_dicts = [dict(r._mapping) for r in rows]

    steps_total   = len(step_dicts)
    steps_applied = sum(1 for r in step_dicts if r["status"] == "applied")
    steps_vetoed  = sum(1 for r in step_dicts if r["status"] == "vetoed")
    steps_failed  = sum(1 for r in step_dicts if r["status"] in ("io_failed", "error"))

    return {
        "mission_id":    mission_id,
        "steps_total":   steps_total,
        "steps_applied": steps_applied,
        "steps_vetoed":  steps_vetoed,
        "steps_failed":  steps_failed,
        "success":       steps_failed == 0 and steps_vetoed == 0 and steps_total > 0,
        "steps":         step_dicts,
    }
