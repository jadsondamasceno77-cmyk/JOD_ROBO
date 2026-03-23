#!/usr/bin/env python3
import asyncio, json, os, time, logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JOD_LOOP")

INTERVAL = int(os.getenv("LOOP_INTERVAL_MINUTES", "5")) * 60

async def tick():
    from intent import execute_intent
    objectives = [
        "Liste todos os agentes ativos",
    ]
    for obj in objectives:
        try:
            r = await execute_intent(obj)
            logger.info(f"[LOOP] {obj[:40]} -> {r.get('execution',{}).get('status','?')}")
        except Exception as e:
            logger.error(f"[LOOP] ERRO: {e}")

async def main():
    logger.info(f"[LOOP] Iniciando loop a cada {INTERVAL//60} minutos")
    while True:
        await tick()
        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
