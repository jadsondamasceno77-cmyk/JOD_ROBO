import httpx
from sqlalchemy import text

from .context import MissionContext, StepResult, StepSpec
from .log import record_step
from .registry import AgentRegistry


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

        await self._reg.ensure_active_finalizer(ctx.finalizer_id)
        if ctx.guardian_id:
            await self._reg.ensure_active_guardian(ctx.guardian_id)

        results: list[StepResult] = []
        for step in ctx.steps:
            result = await self._execute_step(step)
            record_step(
                self._sf,
                ctx.mission_id,
                ctx.mission_id,   # correlation_id = mission_id no MVP
                ctx.finalizer_id,
                ctx.guardian_id,
                step,
                result,
            )
            results.append(result)
            if result.status in ("io_failed", "error"):
                break  # abort-on-first-error

        return results

    async def _execute_step(self, step: StepSpec) -> StepResult:
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
                    # Verificação extra via integration_audit — segurança pós-HTTP-200
                    io_ok = self._verify_io_committed(tid)
                    status = "applied" if io_ok else "io_failed"
                    return StepResult(
                        step=step, status=status,
                        transaction_id=tid,
                        io_committed=1 if io_ok else 0,
                        http_status=200, raw=raw,
                    )
                # Sem guardian — sem integration_audit; confiar no HTTP 200
                return StepResult(
                    step=step, status="applied",
                    io_committed=None,
                    http_status=200, raw=raw,
                )

            # forbidden, needs_approval, not_implemented ou status inesperado
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
