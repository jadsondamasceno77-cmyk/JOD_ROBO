import asyncio
import uuid

import httpx
from sqlalchemy import text

from .context import MissionContext, StepResult, StepSpec
from .log import begin_step, finish_step
from .mission_control import FencingError, MissionControl, run_heartbeat
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

        if decision.action == "QUARANTINE":
            with self._sf() as s:
                MissionControl.quarantine(s, ctx.mission_id, decision.reason)
            raise RuntimeError(
                f"missão {ctx.mission_id} quarentenada: {decision.reason}"
            )

        # decision.action == "RESUME" — resume_from_step é a autoridade do reconcile
        resume_from = decision.resume_from_step  # type: ignore[assignment]

        # ── Fase B: aquisição atômica ────────────────────────────────────────
        # claim: PENDING → RUNNING (primeira execução)
        # takeover: RUNNING+stale → RUNNING (recovery)
        owner_id = str(uuid.uuid4())

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
        # Se houve crash entre begin_step e finish_step com io_committed=1
        # confirmado pelo reconcile, reparar a entrada RUNNING para 'applied'.
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

                log_rowid = begin_step(
                    self._sf,
                    ctx.mission_id,
                    ctx.mission_id,  # correlation_id = mission_id
                    ctx.finalizer_id,
                    ctx.guardian_id,
                    step,
                    step_index,
                )
                result = await self._execute_step(step)
                finish_step(self._sf, log_rowid, result)
                results.append(result)

                if result.status in ("io_failed", "error", "vetoed"):
                    mission_success = False
                if result.status in ("io_failed", "error"):
                    break  # abort-on-first-error

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
            detail = raw.get("detail", {})
            tid = detail.get("guardian_transaction_id") if isinstance(detail, dict) else None
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
