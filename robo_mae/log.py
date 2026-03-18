import json

from sqlalchemy import text


def record_step(
    session_factory,
    mission_id: str,
    correlation_id: str,
    finalizer_id: str,
    guardian_id,
    step,
    result,
) -> None:
    with session_factory() as s:
        s.execute(
            text("""
                INSERT INTO mission_log
                    (mission_id, correlation_id, finalizer_id, guardian_id,
                     action, target_path, status, io_committed,
                     transaction_id, details)
                VALUES
                    (:mission_id, :correlation_id, :finalizer_id, :guardian_id,
                     :action, :target_path, :status, :io_committed,
                     :transaction_id, :details)
            """),
            {
                "mission_id":     mission_id,
                "correlation_id": correlation_id,
                "finalizer_id":   finalizer_id,
                "guardian_id":    guardian_id,
                "action":         step.action,
                "target_path":    step.target_path,
                "status":         result.status,
                "io_committed":   result.io_committed,
                "transaction_id": result.transaction_id,
                "details":        json.dumps(result.raw),
            },
        )
        s.commit()
