import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text

STALE_THRESHOLD_SECS    = 30
HEARTBEAT_INTERVAL_SECS = 10


class FencingError(RuntimeError):
    """Raised when ownership verification fails — execution must stop immediately."""


@dataclass
class ReconcileDecision:
    action:           str            # RESUME | QUARANTINE | NOOP
    resume_from_step: Optional[int]
    reason:           str


def _now_iso() -> str:
    """UTC naive ISO string — compatível com Python 3.10 fromisoformat."""
    return datetime.utcnow().isoformat()


def _is_stale(heartbeat_at: Optional[str]) -> bool:
    if heartbeat_at is None:
        return True
    try:
        hb  = datetime.fromisoformat(heartbeat_at)
        now = datetime.utcnow()
        return (now - hb).total_seconds() > STALE_THRESHOLD_SECS
    except (ValueError, TypeError):
        return True


class MissionControl:

    @staticmethod
    def create(session, mission_id: str) -> None:
        """INSERT OR IGNORE. Idempotente."""
        session.execute(
            text("""
                INSERT OR IGNORE INTO mission_control
                    (mission_id, status, lock_version, current_step, created_at)
                VALUES (:mid, 'PENDING', 0, 0, :now)
            """),
            {"mid": mission_id, "now": _now_iso()},
        )
        session.commit()

    @staticmethod
    def claim(session, mission_id: str, owner_id: str) -> Optional[int]:
        """
        PENDING → RUNNING. Somente para missões em status PENDING.
        Retorna lock_version=1 se sucesso, None se não era PENDING ou lost race.
        """
        result = session.execute(
            text("""
                UPDATE mission_control
                SET status='RUNNING', owner_id=:owner, lock_version=1,
                    claimed_at=:now, heartbeat_at=:now
                WHERE mission_id=:mid AND status='PENDING'
            """),
            {"owner": owner_id, "now": _now_iso(), "mid": mission_id},
        )
        session.commit()
        return 1 if result.rowcount > 0 else None

    @staticmethod
    def takeover(session, mission_id: str, new_owner_id: str) -> Optional[int]:
        """
        RUNNING+stale → RUNNING (novo dono). Somente para missões RUNNING com
        heartbeat stale. Retorna novo lock_version ou None se não elegível.
        """
        row = session.execute(
            text("""
                SELECT lock_version, heartbeat_at
                FROM mission_control
                WHERE mission_id=:mid AND status='RUNNING'
            """),
            {"mid": mission_id},
        ).fetchone()

        if row is None or not _is_stale(row[1]):
            return None

        old_version = row[0]
        new_version = old_version + 1
        now = _now_iso()
        result = session.execute(
            text("""
                UPDATE mission_control
                SET owner_id=:owner, lock_version=:new_ver,
                    claimed_at=:now, heartbeat_at=:now
                WHERE mission_id=:mid AND lock_version=:old_ver AND status='RUNNING'
            """),
            {
                "owner":   new_owner_id,
                "new_ver": new_version,
                "now":     now,
                "mid":     mission_id,
                "old_ver": old_version,
            },
        )
        session.commit()
        return new_version if result.rowcount > 0 else None

    @staticmethod
    def fence(session, mission_id: str, owner_id: str, lock_version: int) -> None:
        """Lança FencingError se ownership foi perdida."""
        row = session.execute(
            text("""
                SELECT owner_id, lock_version
                FROM mission_control WHERE mission_id=:mid
            """),
            {"mid": mission_id},
        ).fetchone()

        if row is None:
            raise FencingError(f"missão {mission_id} não encontrada no mission_control")

        db_owner, db_ver = row
        if db_owner != owner_id or db_ver != lock_version:
            raise FencingError(
                f"fencing falhou: mission={mission_id} "
                f"owner={db_owner!r}/{owner_id!r} version={db_ver}/{lock_version}"
            )

    @staticmethod
    def heartbeat(session, mission_id: str, owner_id: str, lock_version: int) -> bool:
        """Atualiza heartbeat_at. Retorna False se ownership foi perdida."""
        result = session.execute(
            text("""
                UPDATE mission_control SET heartbeat_at=:now
                WHERE mission_id=:mid AND owner_id=:owner AND lock_version=:ver
            """),
            {
                "now":   _now_iso(),
                "mid":   mission_id,
                "owner": owner_id,
                "ver":   lock_version,
            },
        )
        session.commit()
        return result.rowcount > 0

    @staticmethod
    def advance_step(
        session, mission_id: str, owner_id: str, lock_version: int, step_index: int
    ) -> None:
        """Avança current_step com fence implícita."""
        result = session.execute(
            text("""
                UPDATE mission_control SET current_step=:step
                WHERE mission_id=:mid AND owner_id=:owner AND lock_version=:ver
            """),
            {
                "step":  step_index,
                "mid":   mission_id,
                "owner": owner_id,
                "ver":   lock_version,
            },
        )
        session.commit()
        if result.rowcount == 0:
            raise FencingError(
                f"advance_step falhou: ownership perdida para {mission_id}"
            )

    @staticmethod
    def complete(
        session, mission_id: str, owner_id: str, lock_version: int, success: bool
    ) -> None:
        """Marca COMPLETED ou FAILED com fence implícita."""
        final_status = "COMPLETED" if success else "FAILED"
        result = session.execute(
            text("""
                UPDATE mission_control SET status=:status
                WHERE mission_id=:mid AND owner_id=:owner AND lock_version=:ver
            """),
            {
                "status": final_status,
                "mid":    mission_id,
                "owner":  owner_id,
                "ver":    lock_version,
            },
        )
        session.commit()
        if result.rowcount == 0:
            raise FencingError(
                f"complete falhou: ownership perdida para {mission_id}"
            )

    @staticmethod
    def quarantine(session, mission_id: str, reason: str) -> None:
        """
        Marca QUARANTINED explicitamente no mission_control.
        Não altera missões já em estado terminal (COMPLETED, FAILED).
        """
        session.execute(
            text("""
                UPDATE mission_control SET status='QUARANTINED'
                WHERE mission_id=:mid
                  AND status NOT IN ('COMPLETED', 'FAILED')
            """),
            {"mid": mission_id},
        )
        session.commit()

    @staticmethod
    def reconcile(session, mission_id: str) -> ReconcileDecision:
        """
        Autoridade única de decisão de retomada.
        Retorna NOOP | QUARANTINE | RESUME(resume_from_step).
        O executor consome a decisão sem recalcular.
        """
        row = session.execute(
            text("""
                SELECT status, heartbeat_at, current_step
                FROM mission_control WHERE mission_id=:mid
            """),
            {"mid": mission_id},
        ).fetchone()

        # Missão nova — ainda não existe (antes do create())
        if row is None:
            return ReconcileDecision(
                action="RESUME", resume_from_step=0, reason="missão nova"
            )

        status, heartbeat_at, current_step = row

        # Estados terminais — nada a fazer
        if status in ("COMPLETED", "FAILED", "QUARANTINED"):
            return ReconcileDecision(
                action="NOOP", resume_from_step=None, reason=f"status={status}"
            )

        # PENDING — primeira execução ou caiu antes de claimar
        if status == "PENDING":
            return ReconcileDecision(
                action="RESUME", resume_from_step=0, reason="PENDING"
            )

        # RUNNING com heartbeat fresco — outro processo dono, não interferir
        if not _is_stale(heartbeat_at):
            return ReconcileDecision(
                action="NOOP",
                resume_from_step=None,
                reason="RUNNING com heartbeat fresco",
            )

        # RUNNING + stale → consulta último step para decidir
        last = session.execute(
            text("""
                SELECT status, io_committed, step_index
                FROM mission_log
                WHERE mission_id=:mid
                ORDER BY id DESC LIMIT 1
            """),
            {"mid": mission_id},
        ).fetchone()

        if last is None:
            return ReconcileDecision(
                action="RESUME",
                resume_from_step=0,
                reason="RUNNING+stale, sem steps gravados",
            )

        last_status, last_io_committed, last_step_index = last
        step_pos = last_step_index if last_step_index is not None else current_step

        if last_status == "RUNNING":
            if last_io_committed == 1:
                return ReconcileDecision(
                    action="RESUME",
                    resume_from_step=step_pos + 1,
                    reason="RUNNING+io_committed=1 → step aplicado, retomar próximo",
                )
            return ReconcileDecision(
                action="QUARANTINE",
                resume_from_step=None,
                reason=f"RUNNING+io_committed={last_io_committed} → estado ambíguo",
            )

        if last_status in ("applied", "dry_run_ok"):
            return ReconcileDecision(
                action="RESUME",
                resume_from_step=step_pos + 1,
                reason=f"last={last_status} → retomar próximo step",
            )

        if last_status == "error":
            return ReconcileDecision(
                action="RESUME",
                resume_from_step=step_pos,
                reason="last=error → retry",
            )

        if last_status in ("vetoed", "io_failed"):
            return ReconcileDecision(
                action="QUARANTINE",
                resume_from_step=None,
                reason=f"last={last_status} → estado terminal por política",
            )

        return ReconcileDecision(
            action="QUARANTINE",
            resume_from_step=None,
            reason=f"last status desconhecido: {last_status}",
        )


async def run_heartbeat(
    session_factory,
    mission_id:   str,
    owner_id:     str,
    lock_version: int,
    stop_event:   asyncio.Event,
) -> None:
    """Background task: atualiza heartbeat até stop_event ou perda de ownership."""
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_INTERVAL_SECS)
            return  # stop_event setado
        except asyncio.TimeoutError:
            pass

        if stop_event.is_set():
            return

        try:
            with session_factory() as s:
                alive = MissionControl.heartbeat(s, mission_id, owner_id, lock_version)
            if not alive:
                return  # ownership perdida — parar silenciosamente
        except Exception:
            pass
