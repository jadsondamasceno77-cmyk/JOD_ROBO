"""
robo_mae/watchdog.py — MACROBLOCO D

Contratos:
- reconcile() é autoridade única — watchdog NÃO recalcula regras
- QUARANTINE: MissionControl.quarantine()
- FAIL:       reconcile() já gravou FAILED, watchdog apenas contabiliza
- NOOP:       sem ação
- RESUME:     redespacha via redispatch_fn (NÃO executa inline)
- SEM import de memory_service
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy import text

from .mission_control import MissionControl

log = logging.getLogger("jod_robo.watchdog")

WATCHDOG_INTERVAL_SECS: int = int(os.getenv("WATCHDOG_INTERVAL_SECS", "30"))


@dataclass
class WatchdogResult:
    scanned:     int = 0
    resumed:     int = 0
    quarantined: int = 0
    failed:      int = 0
    noop:        int = 0


class WatchdogScanner:
    def __init__(
        self,
        session_factory,
        redispatch_fn: Callable[[str], Awaitable[None]],
    ):
        self._sf  = session_factory
        self._rdf = redispatch_fn

    async def scan_once(self) -> WatchdogResult:
        result = WatchdogResult()

        with self._sf() as s:
            rows = s.execute(
                text("""
                    SELECT mission_id FROM mission_control
                    WHERE status IN ('RUNNING', 'WAITING_APPROVAL')
                """)
            ).fetchall()

        mission_ids = [r[0] for r in rows]
        result.scanned = len(mission_ids)

        for mid in mission_ids:
            with self._sf() as s:
                decision = MissionControl.reconcile(s, mid)

            if decision.action == "QUARANTINE":
                with self._sf() as s:
                    MissionControl.quarantine(s, mid, decision.reason)
                result.quarantined += 1
                log.warning(
                    "watchdog quarantine mission=%s reason=%s", mid, decision.reason
                )

            elif decision.action == "FAIL":
                # reconcile() já persistiu FAILED — watchdog apenas contabiliza
                result.failed += 1
                log.warning(
                    "watchdog fail mission=%s reason=%s", mid, decision.reason
                )

            elif decision.action == "NOOP":
                result.noop += 1

            elif decision.action == "RESUME":
                asyncio.create_task(self._rdf(mid))
                result.resumed += 1
                log.info(
                    "watchdog resume mission=%s reason=%s", mid, decision.reason
                )

        return result

    async def run_loop(self, stop_event: asyncio.Event) -> None:
        log.info("watchdog loop iniciado interval=%ds", WATCHDOG_INTERVAL_SECS)
        try:
            while True:
                try:
                    await self.scan_once()
                except Exception as exc:
                    log.error("watchdog scan_once erro: %s", exc)
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=WATCHDOG_INTERVAL_SECS
                    )
                    break  # stop_event setado
                except asyncio.TimeoutError:
                    pass
        finally:
            log.info("watchdog loop encerrado")
