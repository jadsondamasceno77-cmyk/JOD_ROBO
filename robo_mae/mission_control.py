import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

STALE_THRESHOLD_SECS    = 30
HEARTBEAT_INTERVAL_SECS = 10
CB_MAX_FAILURES         = 5
CB_OPEN_SECS            = 60


class FencingError(RuntimeError):
    """Raised when ownership verification fails — execution must stop immediately."""


@dataclass
class ReconcileDecision:
    action:           str            # RESUME | QUARANTINE | NOOP | FAIL
    resume_from_step: Optional[int]
    reason:           str
    mission_status:   Optional[str] = None  # guia o executor no caminho de aquisição


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


def _commit_failed(session, mission_id: str, reason: str) -> ReconcileDecision:
    """Persiste FAILED no mission_control antes de retornar FAIL. Executor apenas consome."""
    session.execute(
        text("""
            UPDATE mission_control SET status='FAILED'
            WHERE mission_id=:mid
              AND status NOT IN ('COMPLETED','FAILED','QUARANTINED')
        """),
        {"mid": mission_id},
    )
    session.commit()
    return ReconcileDecision(action="FAIL", resume_from_step=None, reason=reason)


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
    def resume_from_approval(session, mission_id: str, owner_id: str) -> Optional[int]:
        """
        WAITING_APPROVAL → RUNNING (nova ownership após aprovação humana).
        Somente para missões em WAITING_APPROVAL.
        Retorna novo lock_version ou None se status não era WAITING_APPROVAL.
        """
        row = session.execute(
            text("""
                SELECT lock_version FROM mission_control
                WHERE mission_id=:mid AND status='WAITING_APPROVAL'
            """),
            {"mid": mission_id},
        ).fetchone()

        if row is None:
            return None

        new_version = row[0] + 1
        now = _now_iso()
        result = session.execute(
            text("""
                UPDATE mission_control
                SET status='RUNNING', owner_id=:owner, lock_version=:new_ver,
                    claimed_at=:now, heartbeat_at=:now
                WHERE mission_id=:mid AND status='WAITING_APPROVAL'
            """),
            {"owner": owner_id, "new_ver": new_version, "now": now, "mid": mission_id},
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
        """Avança current_step com fence implícita. Reseta retry_count e next_retry_at."""
        result = session.execute(
            text("""
                UPDATE mission_control
                SET current_step=:step, retry_count=0, next_retry_at=NULL
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
    def schedule_retry(
        session, mission_id: str, owner_id: str, lock_version: int,
        next_retry_at: str,
    ) -> None:
        """
        Incrementa retry_count e persiste next_retry_at.
        Fence implícita (owner+version). Missão continua RUNNING — heartbeat vai esfriar.
        """
        result = session.execute(
            text("""
                UPDATE mission_control
                SET retry_count=retry_count+1, next_retry_at=:next
                WHERE mission_id=:mid AND owner_id=:owner AND lock_version=:ver
            """),
            {
                "next":  next_retry_at,
                "mid":   mission_id,
                "owner": owner_id,
                "ver":   lock_version,
            },
        )
        session.commit()
        if result.rowcount == 0:
            raise FencingError(
                f"schedule_retry falhou: ownership perdida para {mission_id}"
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
        Reservado para ambiguidade/inconsistência operacional.
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
    def set_waiting_approval(
        session, mission_id: str, owner_id: str, lock_version: int,
        step_index: int, context_snapshot: dict,
        approval_ttl_secs: int = 86400,
    ) -> int:
        """
        INSERT OR IGNORE em approval_requests (UNIQUE(mission_id, step_index)).
        UPDATE mission_control SET status='WAITING_APPROVAL' com fence implícita.
        Retorna approval_request.id.
        """
        now        = _now_iso()
        expires_at = (datetime.utcnow() + timedelta(seconds=approval_ttl_secs)).isoformat()

        session.execute(
            text("""
                INSERT OR IGNORE INTO approval_requests
                    (mission_id, step_index, context_snapshot, status,
                     expires_at, created_at)
                VALUES (:mid, :idx, :ctx, 'PENDING', :exp, :now)
            """),
            {
                "mid": mission_id,
                "idx": step_index,
                "ctx": json.dumps(context_snapshot),
                "exp": expires_at,
                "now": now,
            },
        )
        session.commit()

        row = session.execute(
            text("""
                SELECT id FROM approval_requests
                WHERE mission_id=:mid AND step_index=:idx
            """),
            {"mid": mission_id, "idx": step_index},
        ).fetchone()
        ar_id = row[0]

        # UPDATE mission_control com fence implícita
        result = session.execute(
            text("""
                UPDATE mission_control SET status='WAITING_APPROVAL'
                WHERE mission_id=:mid AND owner_id=:owner AND lock_version=:ver
            """),
            {"mid": mission_id, "owner": owner_id, "ver": lock_version},
        )
        session.commit()
        if result.rowcount == 0:
            raise FencingError(
                f"set_waiting_approval falhou: ownership perdida para {mission_id}"
            )
        return ar_id

    @staticmethod
    def resume_approval(
        session, mission_id: str, step_index: int, decision: str,
        decided_by: str, notes: Optional[str] = None,
    ) -> bool:
        """
        decision: 'approved' | 'denied'
        UPDATE approval_requests se status='PENDING' e não expirado.
        Se denied: fecha exatamente a linha do step em mission_log e mission_control (FAILED).
        Se approved: NÃO toca mission_control — reconcile() é a autoridade de retomada.
        Retorna True se houve row afetada.
        """
        now = _now_iso()
        result = session.execute(
            text("""
                UPDATE approval_requests
                SET status=:decision, decided_at=:now,
                    decided_by=:by, notes=:notes
                WHERE mission_id=:mid AND step_index=:idx
                  AND status='PENDING' AND expires_at > :now
            """),
            {
                "decision": decision, "now": now,
                "by": decided_by, "notes": notes,
                "mid": mission_id, "idx": step_index,
            },
        )
        session.commit()

        if result.rowcount == 0:
            return False

        if decision == "denied":
            # Fechar exatamente a linha do step correspondente (guardrail: step_index preciso)
            session.execute(
                text("""
                    UPDATE mission_log SET status='denied'
                    WHERE mission_id=:mid AND step_index=:idx
                      AND status='pending_approval'
                """),
                {"mid": mission_id, "idx": step_index},
            )
            # Fechar missão formalmente
            session.execute(
                text("""
                    UPDATE mission_control SET status='FAILED'
                    WHERE mission_id=:mid
                      AND status NOT IN ('COMPLETED','FAILED','QUARANTINED')
                """),
                {"mid": mission_id},
            )
            session.commit()

        return True

    @staticmethod
    def expire_approval(session, mission_id: str, step_index: int) -> None:
        """
        Fecha approval_requests (expired), exatamente a linha mission_log (expired),
        e mission_control (FAILED). Usa step_index para precisão em mission_log.
        """
        now = _now_iso()
        session.execute(
            text("""
                UPDATE approval_requests SET status='expired', decided_at=:now
                WHERE mission_id=:mid AND step_index=:idx AND status='PENDING'
            """),
            {"now": now, "mid": mission_id, "idx": step_index},
        )
        # Guardrail: usar step_index para fechar exatamente a linha correta
        session.execute(
            text("""
                UPDATE mission_log SET status='expired'
                WHERE mission_id=:mid AND step_index=:idx
                  AND status='pending_approval'
            """),
            {"mid": mission_id, "idx": step_index},
        )
        session.execute(
            text("""
                UPDATE mission_control SET status='FAILED'
                WHERE mission_id=:mid
                  AND status NOT IN ('COMPLETED','FAILED','QUARANTINED')
            """),
            {"mid": mission_id},
        )
        session.commit()

    @staticmethod
    def reconcile(session, mission_id: str) -> ReconcileDecision:
        """
        Autoridade única de decisão de retomada.
        Retorna NOOP | QUARANTINE | RESUME | FAIL.
        O executor consome a decisão sem recalcular.
        """
        row = session.execute(
            text("""
                SELECT status, heartbeat_at, current_step,
                       retry_count, max_retries, next_retry_at
                FROM mission_control WHERE mission_id=:mid
            """),
            {"mid": mission_id},
        ).fetchone()

        # Missão nova — ainda não existe (antes do create())
        if row is None:
            return ReconcileDecision(
                action="RESUME", resume_from_step=0, reason="missão nova"
            )

        status, heartbeat_at, current_step, retry_count, max_retries, next_retry_at = row

        # Estados terminais — nada a fazer
        if status in ("COMPLETED", "FAILED", "QUARANTINED"):
            return ReconcileDecision(
                action="NOOP", resume_from_step=None, reason=f"status={status}"
            )

        # WAITING_APPROVAL — verificar estado do approval
        if status == "WAITING_APPROVAL":
            ar = session.execute(
                text("""
                    SELECT status, step_index, expires_at FROM approval_requests
                    WHERE mission_id=:mid ORDER BY id DESC LIMIT 1
                """),
                {"mid": mission_id},
            ).fetchone()

            if ar is None:
                return _commit_failed(session, mission_id,
                                      "WAITING_APPROVAL sem approval_request")

            ar_status, ar_step_index, expires_at = ar

            if ar_status == "approved":
                return ReconcileDecision(
                    action="RESUME", resume_from_step=ar_step_index,
                    mission_status="WAITING_APPROVAL",
                    reason="approval aprovado",
                )
            if ar_status in ("denied", "expired"):
                # Já persistido por resume_approval/expire_approval — FAILED já gravado
                return ReconcileDecision(
                    action="NOOP", resume_from_step=None, reason=f"approval_{ar_status}"
                )
            # PENDING — verificar expiração
            if _now_iso() > expires_at:
                MissionControl.expire_approval(session, mission_id, ar_step_index)
                return ReconcileDecision(
                    action="FAIL", resume_from_step=None, reason="approval_expired"
                )
            return ReconcileDecision(
                action="NOOP", resume_from_step=None, reason="awaiting_approval"
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
            mr = max_retries if max_retries is not None else 3
            rc = retry_count if retry_count is not None else 0
            if rc >= mr:
                return _commit_failed(
                    session, mission_id, f"retries_exhausted: {rc}/{mr}"
                )
            if next_retry_at is not None and _now_iso() < next_retry_at:
                return ReconcileDecision(
                    action="NOOP",
                    resume_from_step=None,
                    reason=f"backoff_active until {next_retry_at}",
                )
            return ReconcileDecision(
                action="RESUME",
                resume_from_step=step_pos,
                reason=f"retry {rc + 1}/{mr}",
            )

        if last_status == "pending_approval":
            # RUNNING+stale com step pendente de aprovação
            ar = session.execute(
                text("""
                    SELECT status, expires_at FROM approval_requests
                    WHERE mission_id=:mid AND step_index=:idx
                    ORDER BY id DESC LIMIT 1
                """),
                {"mid": mission_id, "idx": step_pos},
            ).fetchone()

            if ar is None:
                return _commit_failed(session, mission_id,
                                      "pending_approval sem approval_request")

            ar_status, expires_at = ar

            if ar_status == "approved":
                return ReconcileDecision(
                    action="RESUME", resume_from_step=step_pos,
                    mission_status="WAITING_APPROVAL",
                    reason="approval aprovado (via RUNNING+stale)",
                )
            if ar_status in ("denied", "expired"):
                return ReconcileDecision(
                    action="NOOP", resume_from_step=None, reason=f"approval_{ar_status}"
                )
            if _now_iso() > expires_at:
                MissionControl.expire_approval(session, mission_id, step_pos)
                return ReconcileDecision(
                    action="FAIL", resume_from_step=None, reason="approval_expired"
                )
            return ReconcileDecision(
                action="NOOP", resume_from_step=None, reason="awaiting_approval"
            )

        if last_status in ("vetoed", "io_failed"):
            return ReconcileDecision(
                action="QUARANTINE",
                resume_from_step=None,
                reason=f"last={last_status} → estado terminal por política",
            )

        if last_status in ("denied", "expired"):
            # mission_control deveria já ser FAILED — garantir formal
            return _commit_failed(session, mission_id, f"last={last_status}")

        return ReconcileDecision(
            action="QUARANTINE",
            resume_from_step=None,
            reason=f"last status desconhecido: {last_status}",
        )


class CircuitBreaker:
    """
    Proteção por (provider_id, operation). provider_id = finalizer_id, operation = action.
    Estados: CLOSED | OPEN | HALF_OPEN
    """

    @staticmethod
    def check(session, provider_id: str, operation: str) -> str:
        row = session.execute(
            text("""
                SELECT state, failures, opened_at
                FROM circuit_breaker
                WHERE provider_id=:pid AND operation=:op
            """),
            {"pid": provider_id, "op": operation},
        ).fetchone()

        if row is None:
            return "CLOSED"

        state, _failures, opened_at = row

        if state == "OPEN" and opened_at is not None:
            try:
                elapsed = (
                    datetime.utcnow() - datetime.fromisoformat(opened_at)
                ).total_seconds()
                if elapsed >= CB_OPEN_SECS:
                    session.execute(
                        text("""
                            UPDATE circuit_breaker SET state='HALF_OPEN'
                            WHERE provider_id=:pid AND operation=:op
                        """),
                        {"pid": provider_id, "op": operation},
                    )
                    session.commit()
                    return "HALF_OPEN"
            except (ValueError, TypeError):
                pass

        return state

    @staticmethod
    def record_success(session, provider_id: str, operation: str) -> None:
        session.execute(
            text("""
                INSERT OR REPLACE INTO circuit_breaker
                    (provider_id, operation, state, failures, opened_at)
                VALUES (:pid, :op, 'CLOSED', 0, NULL)
            """),
            {"pid": provider_id, "op": operation},
        )
        session.commit()

    @staticmethod
    def record_failure(session, provider_id: str, operation: str) -> None:
        now = _now_iso()
        row = session.execute(
            text("""
                SELECT failures FROM circuit_breaker
                WHERE provider_id=:pid AND operation=:op
            """),
            {"pid": provider_id, "op": operation},
        ).fetchone()

        new_failures = (row[0] if row else 0) + 1
        new_state    = "OPEN" if new_failures >= CB_MAX_FAILURES else "CLOSED"
        opened_at    = now if new_state == "OPEN" else None

        session.execute(
            text("""
                INSERT OR REPLACE INTO circuit_breaker
                    (provider_id, operation, state, failures, opened_at)
                VALUES (:pid, :op, :state, :failures, :opened_at)
            """),
            {
                "pid": provider_id, "op": operation,
                "state": new_state, "failures": new_failures,
                "opened_at": opened_at,
            },
        )
        session.commit()


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
