import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("JOD_ORCHESTRATOR")

BASE_URL = "http://localhost:37777"
HEADERS = {
    "Content-Type": "application/json",
    "x-trust-token": "jod_robo_trust_2026_secure",
}

import httpx

async def call(method, path, payload=None, idem_key=None, req_id=None):
    h = {**HEADERS}
    h["x-request-id"] = req_id or str(uuid.uuid4())[:8] + "00"
    h["x-idempotency-key"] = idem_key or str(uuid.uuid4())
    async with httpx.AsyncClient() as client:
        if method == "POST":
            r = await client.post(f"{BASE_URL}{path}", headers=h, json=payload)
        else:
            r = await client.get(f"{BASE_URL}{path}", headers=h)
    return r.json()

async def wait_task(task_id, req_base):
    for i in range(10):
        await asyncio.sleep(0.5)
        r = await call("GET", f"/tasks/{task_id}", req_id=f"{req_base}-chk{i}")
        if r.get("status") in ("succeeded", "failed", "rolled_back"):
            return r
    return {"status": "timeout"}

async def run_flow(plan: dict):
    flow_id = str(uuid.uuid4())[:8]
    logger.info(f"[FLOW {flow_id}] INICIANDO — {plan}")

    # FASE 1: PLANNER planeja
    logger.info(f"[FLOW {flow_id}] FASE 1 — Planner gerando plano")
    plan_payload = {
        "flow_id": flow_id,
        "action": plan.get("action"),
        "params": plan.get("params", {}),
        "requested_at": datetime.now(timezone.utc).isoformat()
    }

    # FASE 2: GUARDIAO audita o plano
    logger.info(f"[FLOW {flow_id}] FASE 2 — Guardiao auditando plano")
    audit_result = await audit_plan(plan_payload)
    if not audit_result["approved"]:
        logger.warning(f"[FLOW {flow_id}] BLOQUEADO pelo Guardiao: {audit_result['reason']}")
        return {"status": "blocked", "reason": audit_result["reason"], "flow_id": flow_id}

    logger.info(f"[FLOW {flow_id}] FASE 2 — Plano aprovado pelo Guardiao")

    # FASE 3: FINALIZADOR executa
    logger.info(f"[FLOW {flow_id}] FASE 3 — Finalizador executando")
    exec_result = await execute_plan(plan_payload, flow_id)

    # FASE 4: GUARDIAO valida resultado
    logger.info(f"[FLOW {flow_id}] FASE 4 — Guardiao validando resultado")
    validation = await validate_result(exec_result)

    # FASE 5: AUDITORIA
    await register_audit(flow_id, plan_payload, exec_result, validation)

    logger.info(f"[FLOW {flow_id}] CONCLUIDO — status: {exec_result.get('status')}")
    return {
        "flow_id": flow_id,
        "approved": audit_result["approved"],
        "execution": exec_result,
        "validation": validation,
        "audit_registered": True
    }

async def audit_plan(plan: dict) -> dict:
    action = plan.get("action", "")
    blocked_actions = ["delete_all", "drop_database", "rm_rf", "override_manifest"]
    if action in blocked_actions:
        return {"approved": False, "reason": f"Acao bloqueada pela politica: {action}"}
    if not plan.get("flow_id"):
        return {"approved": False, "reason": "flow_id ausente — contrato invalido"}
    return {"approved": True, "reason": "ok", "risk_score": 0.1}

async def execute_plan(plan: dict, flow_id: str) -> dict:
    action = plan.get("action")
    params = plan.get("params", {})
    try:
        if action == "create_agent":
            idem = f"orch-create-{flow_id}"
            r = await call("POST", "/agents/create-from-template", {
                "action_type": "create_agent_from_template",
                "parameters": {
                    "template_name": params.get("template", "executor"),
                    "new_agent_id": params.get("agent_id"),
                    "name": params.get("name", params.get("agent_id"))
                }
            }, idem_key=idem, req_id=f"{flow_id}-exec")
            task_id = r.get("task_id")
            result = await wait_task(task_id, flow_id)
            return {"status": result.get("status"), "result": result.get("result"), "action": action}

        elif action == "validate_agent":
            idem = f"orch-val-{flow_id}"
            r = await call("POST", "/agents/validate", {
                "action_type": "validate_agent",
                "parameters": {"agent_id": params.get("agent_id")}
            }, idem_key=idem, req_id=f"{flow_id}-val")
            task_id = r.get("task_id")
            result = await wait_task(task_id, flow_id)
            return {"status": result.get("status"), "result": result.get("result"), "action": action}

        elif action == "activate_agent":
            idem = f"orch-act-{flow_id}"
            r = await call("POST", "/agents/activate", {
                "action_type": "activate_agent",
                "parameters": {"agent_id": params.get("agent_id")}
            }, idem_key=idem, req_id=f"{flow_id}-act")
            task_id = r.get("task_id")
            result = await wait_task(task_id, flow_id)
            return {"status": result.get("status"), "result": result.get("result"), "action": action}

        elif action == "list_agents":
            r = await call("GET", "/agents", req_id=f"{flow_id}-list")
            return {"status": "succeeded", "result": r, "action": action}

        else:
            return {"status": "failed", "result": {"error": f"Acao desconhecida: {action}"}, "action": action}

    except Exception as e:
        return {"status": "failed", "result": {"error": str(e)}, "action": action}

async def validate_result(exec_result: dict) -> dict:
    if exec_result.get("status") == "succeeded":
        return {"valid": True, "score": 1.0}
    return {"valid": False, "score": 0.0, "reason": exec_result.get("result", {}).get("error", "unknown")}

async def register_audit(flow_id, plan, exec_result, validation):
    audit_path = Path("/home/jod_robo/JOD_ROBO/memory/audit_flow.jsonl")
    entry = {
        "flow_id": flow_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "execution_status": exec_result.get("status"),
        "validation": validation
    }
    with open(audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

async def main():
    print("\n=== TESTE DO ORQUESTRADOR JOD_ROBO ===\n")

    r1 = await run_flow({"action": "list_agents", "params": {}})
    print(f"[1] list_agents: {json.dumps(r1, indent=2)}")

    r2 = await run_flow({"action": "delete_all", "params": {}})
    print(f"[2] delete_all (deve bloquear): {json.dumps(r2, indent=2)}")

    r3 = await run_flow({
        "action": "create_agent",
        "params": {"template": "support", "agent_id": "agente_suporte_01", "name": "Agente Suporte 01"}
    })
    print(f"[3] create_agent: {json.dumps(r3, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())
