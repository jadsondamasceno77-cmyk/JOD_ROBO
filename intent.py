#!/usr/bin/env python3
import asyncio, json, os, sys
from pathlib import Path
from brain import think
from orchestrator import run_flow
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

async def execute_intent(objective: str):
    print(f"INTENT: {objective}")
    brain_result = await think(objective)
    plan = brain_result["plan"]
    guard = brain_result["guard"]
    if not guard.get("approved"):
        return {"status": "blocked", "reason": guard.get("reason")}
    return await run_flow({"action": plan["action"], "params": plan.get("params", {})})

async def main():
    objectives = sys.argv[1:] or ["Liste todos os agentes ativos"]
    for obj in objectives:
        r = await execute_intent(obj)
        print(json.dumps(r, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
