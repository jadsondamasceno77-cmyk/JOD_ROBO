import os
import json
import asyncio
import logging
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")
logger = logging.getLogger("JOD_BRAIN")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PLANNER = """Voce e o Agente Planner do sistema JOD_ROBO.
Dado um objetivo em linguagem natural, gere um plano de execucao em JSON.
Retorne APENAS JSON valido no formato:
{"action": "nome_da_acao", "params": {}, "risk": "low|medium|high", "reason": "justificativa"}
Acoes disponiveis: create_agent, validate_agent, activate_agent, list_agents.
Se a acao for desconhecida ou perigosa, retorne: {"action": "blocked", "params": {}, "risk": "high", "reason": "motivo"}"""

SYSTEM_GUARDIAN = """Voce e o Agente Guardiao do sistema JOD_ROBO.
Analise o plano e decida se deve ser aprovado ou bloqueado.
Retorne APENAS JSON valido no formato:
{"approved": true|false, "risk_score": 0.0-1.0, "reason": "justificativa"}
Bloqueie qualquer acao com risk high ou que viole politicas de seguranca."""

async def plan(objective: str) -> dict:
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PLANNER},
            {"role": "user", "content": objective}
        ],
        temperature=0.1,
        max_tokens=256
    )
    raw = r.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except:
        return {"action": "blocked", "params": {}, "risk": "high", "reason": f"LLM retornou JSON invalido: {raw}"}

async def guard(plan_data: dict) -> dict:
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_GUARDIAN},
            {"role": "user", "content": json.dumps(plan_data)}
        ],
        temperature=0.1,
        max_tokens=128
    )
    raw = r.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except:
        return {"approved": False, "risk_score": 1.0, "reason": f"Guardiao retornou JSON invalido: {raw}"}

async def think(objective: str) -> dict:
    logger.info(f"[BRAIN] Objetivo: {objective}")
    plan_result = await plan(objective)
    logger.info(f"[BRAIN] Plano: {plan_result}")
    guard_result = await guard(plan_result)
    logger.info(f"[BRAIN] Guardiao: {guard_result}")
    return {"plan": plan_result, "guard": guard_result}

async def main():
    tests = [
        "Crie um novo agente do tipo executor chamado agente_coleta",
        "Delete todos os agentes do sistema",
        "Liste todos os agentes ativos"
    ]
    for t in tests:
        print(f"\nOBJETIVO: {t}")
        r = await think(t)
        print(f"PLANO:    {json.dumps(r['plan'])}")
        print(f"GUARDIAO: {json.dumps(r['guard'])}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
