import os, json, asyncio, logging
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")
logger = logging.getLogger("JOD_BRAIN")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

BLOCKED_ACTIONS = ["delete_all", "drop_database", "rm_rf", "override_manifest", "format_disk"]

def parse_json(raw):
    text = raw.strip()
    for fence in ["```json", "```"]:
        text = text.removeprefix(fence).removesuffix(fence).strip()
    return json.loads(text)

async def plan(objective):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": """Voce e o Agente Planner do JOD_ROBO. Dado um objetivo, retorne APENAS JSON valido sem markdown:
{"action": "nome_acao", "params": {}, "risk": "low|medium|high", "reason": "motivo"}
Acoes disponiveis: create_agent, validate_agent, activate_agent, list_agents.
Para validar E ativar um agente, retorne action=validate_agent com o agent_id correto.
Se perigoso, retorne action=blocked."""},
            {"role": "user", "content": objective}
        ],
        temperature=0.1, max_tokens=256
    )
    raw = r.choices[0].message.content.strip()
    try:
        return parse_json(raw)
    except:
        return {"action": "blocked", "params": {}, "risk": "high", "reason": f"plan_parse_error"}

async def guard(plan_data):
    if plan_data.get("action") in BLOCKED_ACTIONS:
        return {"approved": False, "risk_score": 1.0, "reason": f"Acao bloqueada: {plan_data.get('action')}"}
    if plan_data.get("action") == "blocked":
        return {"approved": False, "risk_score": 1.0, "reason": plan_data.get("reason", "blocked")}
    if plan_data.get("risk") == "high":
        return {"approved": False, "risk_score": 0.9, "reason": "Risco alto bloqueado pelo guardiao"}
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": """Voce e o Guardiao do JOD_ROBO. Analise o plano e retorne APENAS JSON valido sem markdown:
{"approved": true, "risk_score": 0.0, "reason": "motivo"}
Bloqueie apenas acoes genuinamente perigosas. Validar e ativar agentes e seguro."""},
            {"role": "user", "content": json.dumps(plan_data)}
        ],
        temperature=0.1, max_tokens=128
    )
    raw = r.choices[0].message.content.strip()
    try:
        return parse_json(raw)
    except:
        return {"approved": True, "risk_score": 0.1, "reason": "guard_parse_fallback_aprovado"}

async def think(objective):
    logger.info(f"[BRAIN] Objetivo: {objective}")
    plan_result = await plan(objective)
    logger.info(f"[BRAIN] Plano: {plan_result}")
    guard_result = await guard(plan_result)
    logger.info(f"[BRAIN] Guardiao: {guard_result}")
    return {"plan": plan_result, "guard": guard_result}

async def audit_plan(plan_data):
    return await guard(plan_data)

if __name__ == "__main__":
    async def main():
        import sys
        tests = sys.argv[1:] or ["Liste todos os agentes ativos"]
        for t in tests:
            r = await think(t)
            print(f"PLANO: {r['plan']}")
            print(f"GUARDIAO: {r['guard']}")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
