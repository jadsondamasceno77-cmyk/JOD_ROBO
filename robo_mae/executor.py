import asyncio
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import text

from .context import MissionContext, StepResult, StepSpec
from .log import begin_step, finish_step
from .mission_control import (
    CircuitBreaker,
    FencingError,
    MissionControl,
    _now_iso,
    run_heartbeat,
)
from .registry import AgentRegistry

# Per-path lock registry — serializa missões concorrentes no mesmo target_path
_exec_path_locks: dict[str, asyncio.Lock] = {}
_exec_path_locks_mutex: asyncio.Lock = asyncio.Lock()


async def _get_exec_path_lock(target_path: str) -> asyncio.Lock:
    async with _exec_path_locks_mutex:
        if target_path not in _exec_path_locks:
            _exec_path_locks[target_path] = asyncio.Lock()
        return _exec_path_locks[target_path]


class MissionExecutor:
    def __init__(
        self,
        ctx: MissionContext,
        registry: AgentRegistry,
        session_factory,
        http_client: httpx.AsyncClient,
        base_url: str,
        headers: dict,
    ):
        self._ctx  = ctx
        self._reg  = registry
        self._sf   = session_factory
        self._http = http_client
        self._base = base_url
        self._hdrs = headers

    async def run(self) -> list[StepResult]:
        ctx = self._ctx

        # ── Fase A: decisão ─────────────────────────────────────────────────
        with self._sf() as s:
            MissionControl.create(s, ctx.mission_id)

        with self._sf() as s:
            decision = MissionControl.reconcile(s, ctx.mission_id)

        if decision.action == "NOOP":
            raise RuntimeError(
                f"missão {ctx.mission_id}: {decision.reason}"
            )

        if decision.action == "FAIL":
            # mission_control.status já é FAILED — persistido pelo reconcile()
            raise RuntimeError(
                f"missão {ctx.mission_id}: {decision.reason}"
            )

        if decision.action == "QUARANTINE":
            with self._sf() as s:
                MissionControl.quarantine(s, ctx.mission_id, decision.reason)
            raise RuntimeError(
                f"missão {ctx.mission_id} quarentenada: {decision.reason}"
            )

        # decision.action == "RESUME"
        resume_from = decision.resume_from_step  # type: ignore[assignment]

        # ── Fase B: aquisição atômica (três caminhos sem sobreposição) ───────
        # resume_from_approval: WAITING_APPROVAL → RUNNING
        # claim:                PENDING           → RUNNING
        # takeover:             RUNNING+stale     → RUNNING
        owner_id = str(uuid.uuid4())

        if decision.mission_status == "WAITING_APPROVAL":
            with self._sf() as s:
                lock_version = MissionControl.resume_from_approval(s, ctx.mission_id, owner_id)
        else:
            with self._sf() as s:
                lock_version = MissionControl.claim(s, ctx.mission_id, owner_id)
            if lock_version is None:
                with self._sf() as s:
                    lock_version = MissionControl.takeover(s, ctx.mission_id, owner_id)

        if lock_version is None:
            raise RuntimeError(
                f"ownership não adquirida para {ctx.mission_id}: race condition"
            )

        # ── Fase C: repair pré-execução ──────────────────────────────────────
        if resume_from > 0:
            with self._sf() as s:
                s.execute(
                    text("""
                        UPDATE mission_log
                        SET status='applied', io_committed=1
                        WHERE mission_id=:mid
                          AND step_index=:idx
                          AND status='RUNNING'
                    """),
                    {"mid": ctx.mission_id, "idx": resume_from - 1},
                )
                s.commit()

        # ── Fase D: ativação de agentes ──────────────────────────────────────
        await self._reg.ensure_active_finalizer(ctx.finalizer_id)
        if ctx.guardian_id:
            await self._reg.ensure_active_guardian(ctx.guardian_id)

        # ── Fase E: loop de execução ─────────────────────────────────────────
        stop_event = asyncio.Event()
        hb_task = asyncio.create_task(
            run_heartbeat(self._sf, ctx.mission_id, owner_id, lock_version, stop_event)
        )

        results:           list[StepResult] = []
        completed_normally = False
        mission_success    = True

        try:
            for step_index, step in enumerate(ctx.steps):
                if step_index < resume_from:
                    continue  # pular steps já confirmados pelo reconcile

                with self._sf() as s:
                    MissionControl.fence(s, ctx.mission_id, owner_id, lock_version)

                with self._sf() as s:
                    MissionControl.advance_step(
                        s, ctx.mission_id, owner_id, lock_version, step_index
                    )

                # Ler estado atual de retry do banco
                with self._sf() as s:
                    mc_row = s.execute(
                        text("""
                            SELECT retry_count, max_retries, retry_delay_secs
                            FROM mission_control WHERE mission_id=:mid
                        """),
                        {"mid": ctx.mission_id},
                    ).fetchone()

                current_rc = (mc_row[0] or 0) if mc_row else 0
                max_r      = (mc_row[1] if mc_row[1] is not None else ctx.max_retries) if mc_row else ctx.max_retries
                delay_s    = (mc_row[2] if mc_row[2] is not None else ctx.retry_delay_secs) if mc_row else ctx.retry_delay_secs

                log_rowid = begin_step(
                    self._sf,
                    ctx.mission_id,
                    ctx.mission_id,  # correlation_id = mission_id
                    ctx.finalizer_id,
                    ctx.guardian_id,
                    step,
                    step_index,
                    retry_count=current_rc,
                )

                # Circuit breaker pre-check (keyed por provider_id + operation)
                cb_blocked = False
                if step.target_path:
                    with self._sf() as s:
                        cb_state = CircuitBreaker.check(
                            s, self._ctx.finalizer_id, step.action
                        )
                    if cb_state == "OPEN":
                        result = StepResult(
                            step=step, status="error",
                            raw={"error": "circuit_open"},
                        )
                        cb_blocked = True

                if not cb_blocked:
                    result = await self._execute_step(step)
                    if step.target_path:
                        with self._sf() as s:
                            if result.status in ("applied", "dry_run_ok"):
                                CircuitBreaker.record_success(
                                    s, self._ctx.finalizer_id, step.action
                                )
                            elif result.status == "error":
                                CircuitBreaker.record_failure(
                                    s, self._ctx.finalizer_id, step.action
                                )

                finish_step(self._sf, log_rowid, result)
                results.append(result)

                # ── Tratamento pós-step ──────────────────────────────────────

                if result.status == "pending_approval":
                    # Pausa formal — nenhum complete() é chamado
                    with self._sf() as s:
                        MissionControl.set_waiting_approval(
                            s, ctx.mission_id, owner_id, lock_version,
                            step_index=step_index,
                            context_snapshot={
                                "mission_id":   ctx.mission_id,
                                "step_index":   step_index,
                                "action":       step.action,
                                "target_path":  step.target_path,
                                "payload":      step.payload,
                                "guardian_id":  ctx.guardian_id,
                                "finalizer_id": ctx.finalizer_id,
                            },
                            approval_ttl_secs=ctx.approval_ttl_secs,
                        )
                    completed_normally = False
                    break

                # vetoed: mission_success=False, loop continua (não aborta)
                if result.status == "vetoed":
                    mission_success = False
                    continue

                if result.status == "io_failed":
                    mission_success = False
                    break  # terminal — não retryável

                if result.status == "error":
                    mission_success = False
                    if current_rc >= max_r:
                        # Retries esgotados em execução ativa → complete() chamado → FAILED
                        completed_normally = True
                    else:
                        # Agendar retry — heartbeat vai esfriar; reconcile retoma quando vencer
                        next_ts = (
                            datetime.utcnow()
                            + timedelta(seconds=delay_s * (2 ** current_rc))
                        ).isoformat()
                        with self._sf() as s:
                            MissionControl.schedule_retry(
                                s, ctx.mission_id, owner_id, lock_version, next_ts
                            )
                        completed_normally = False
                    break

            else:
                # Loop completou sem break
                completed_normally = True

        except FencingError:
            completed_normally = False
            raise

        finally:
            stop_event.set()
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass

            if completed_normally:
                try:
                    with self._sf() as s:
                        MissionControl.complete(
                            s, ctx.mission_id, owner_id, lock_version, mission_success
                        )
                except FencingError:
                    pass  # ownership perdida no último momento — reconciliador decide

        return results

    async def _execute_step(self, step: StepSpec) -> StepResult:
        """Adquire lock por target_path antes de disparar o request de execução."""
        if step.target_path is not None:
            path_lock = await _get_exec_path_lock(step.target_path)
            async with path_lock:
                return await self._do_execute(step)
        return await self._do_execute(step)

    async def _do_execute(self, step: StepSpec) -> StepResult:
        body: dict = {
            "mode":   step.mode,
            "action": step.action,
        }
        if step.target_path is not None:
            body["target_path"] = step.target_path
        if step.payload is not None:
            body["payload"] = step.payload
        if self._ctx.guardian_id:
            body["guardian_id"] = self._ctx.guardian_id

        try:
            r = await self._http.post(
                f"{self._base}/agents/{self._ctx.finalizer_id}/finalizer/execute",
                headers=self._hdrs,
                json=body,
            )
        except Exception as exc:
            return StepResult(step=step, status="error", raw={"error": str(exc)})

        try:
            raw = r.json()
        except Exception:
            raw = {"raw_text": r.text}

        if r.status_code == 200:
            resp_status = raw.get("status", "")

            if resp_status == "dry_run_ok":
                return StepResult(
                    step=step, status="dry_run_ok",
                    http_status=200, raw=raw,
                )

            if resp_status == "applied":
                evidence = raw.get("evidence") or {}
                tid = evidence.get("guardian_transaction_id")
                if tid:
                    io_ok = self._verify_io_committed(tid)
                    status = "applied" if io_ok else "io_failed"
                    return StepResult(
                        step=step, status=status,
                        transaction_id=tid,
                        io_committed=1 if io_ok else 0,
                        http_status=200, raw=raw,
                    )
                return StepResult(
                    step=step, status="applied",
                    io_committed=None,
                    http_status=200, raw=raw,
                )

            return StepResult(step=step, status="error", http_status=200, raw=raw)

        if r.status_code == 403:
            # guardian_status é o campo real (não "reason") — está dentro de detail
            detail = raw.get("detail", {})
            if isinstance(detail, dict):
                guardian_status = detail.get("guardian_status", "")
                tid             = detail.get("guardian_transaction_id")
            else:
                guardian_status = ""
                tid             = None

            if guardian_status == "needs_approval":
                return StepResult(
                    step=step, status="pending_approval",
                    http_status=403, raw=raw,
                )

            # guardian_status == "blocked" ou qualquer outro 403
            return StepResult(
                step=step, status="vetoed",
                transaction_id=tid,
                io_committed=0,
                http_status=403, raw=raw,
            )

        return StepResult(step=step, status="error", http_status=r.status_code, raw=raw)

    def _verify_io_committed(self, transaction_id: str) -> bool:
        with self._sf() as s:
            row = s.execute(
                text(
                    "SELECT io_committed FROM integration_audit "
                    "WHERE transaction_id = :tid"
                ),
                {"tid": transaction_id},
            ).fetchone()
        return bool(row[0]) if row else False
