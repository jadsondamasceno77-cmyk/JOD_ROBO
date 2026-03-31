#!/usr/bin/env python3
"""
JOD_ROBO — Agente N8N v2.0
Executor real: cria, lista, ativa e deleta workflows no n8n via API REST.
Faixa preta: todos os 6 pilares do n8n Expert.
Compatível com n8n v2.x
"""

import asyncio, json, os
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
N8N_KEY = os.getenv("N8N_API_KEY", "")
HEADERS = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}

# ─── API CALLS ──────────────────────────────────────────────────────────────────

async def n8n_get(path):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{N8N_URL}/api/v1{path}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def n8n_post(path, payload):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        if not r.is_success:
            raise Exception(f"n8n API error {r.status_code}: {r.text}")
        return r.json()

async def n8n_put(path, payload):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()
async def n8n_patch(path, payload):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()

async def n8n_delete(path):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.delete(f"{N8N_URL}/api/v1{path}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

# ─── OPERAÇÕES ──────────────────────────────────────────────────────────────────

async def list_workflows():
    r = await n8n_get("/workflows")
    return [{"id": w["id"], "name": w["name"], "active": w["active"]} for w in r.get("data", [])]

async def get_workflow(wf_id):
    return await n8n_get(f"/workflows/{wf_id}")

async def create_workflow(name, nodes, connections, active=False):
    payload = {"name": name, "nodes": nodes, "connections": connections,
                "settings": {"executionOrder": "v1"}}
    return await n8n_post("/workflows", payload)

async def activate_workflow(wf_id):
    return await n8n_patch(f"/workflows/{wf_id}", {"active": True})

async def deactivate_workflow(wf_id):
    return await n8n_patch(f"/workflows/{wf_id}", {"active": False})

async def delete_workflow(wf_id):
    return await n8n_delete(f"/workflows/{wf_id}")

async def list_executions(wf_id=None, limit=10):
    path = f"/executions?limit={limit}"
    if wf_id: path += f"&workflowId={wf_id}"
    return await n8n_get(path)

# ─── TEMPLATES COMPATÍVEIS COM N8N v2 ───────────────────────────────────────────

def tpl_manual_trigger():
    """Node de trigger manual — base para qualquer workflow."""
    return {
        "id": "manual-trigger",
        "name": "When clicking 'Test workflow'",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [250, 300],
        "parameters": {}
    }

def tpl_webhook(path="jod-webhook", method="GET"):
    return {
        "id": "webhook-node",
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [250, 300],
        "parameters": {
            "path": path,
            "httpMethod": method,
            "responseMode": "onReceived",
            "responseData": "allEntries"
        }
    }

def tpl_http_request(url, method="GET"):
    return {
        "id": "http-node",
        "name": "HTTP Request",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [500, 300],
        "parameters": {"url": url, "method": method}
    }

def tpl_code(js_code):
    return {
        "id": "code-node",
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [500, 300],
        "parameters": {
            "jsCode": js_code,
            "mode": "runOnceForAllItems"
        }
    }

def tpl_schedule(cron="0 9 * * 1-5"):
    return {
        "id": "schedule-node",
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [250, 300],
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": cron}]}
        }
    }

def tpl_set(fields: dict):
    """Set node para definir valores."""
    assignments = [{"id": f"field-{i}", "name": k, "value": v, "type": "string"}
                   for i, (k, v) in enumerate(fields.items())]
    return {
        "id": "set-node",
        "name": "Set",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [500, 300],
        "parameters": {
            "mode": "manual",
            "assignments": {"assignments": assignments}
        }
    }

def tpl_if(condition_left, operator, condition_right):
    """IF node para lógica condicional."""
    return {
        "id": "if-node",
        "name": "IF",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [500, 300],
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True},
                "conditions": [{
                    "id": "cond-1",
                    "leftValue": condition_left,
                    "rightValue": condition_right,
                    "operator": {"type": "string", "operation": operator}
                }]
            }
        }
    }

def tpl_error_trigger():
    return {
        "id": "error-trigger",
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": [250, 300],
        "parameters": {}
    }

def tpl_respond_webhook(response="={{ $json }}"):
    return {
        "id": "respond-node",
        "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [750, 300],
        "parameters": {"respondWith": "json", "responseBody": response}
    }

# ─── WORKFLOWS PRONTOS ──────────────────────────────────────────────────────────

async def create_webhook_http(webhook_path="jod-webhook", target_url="https://httpbin.org/post"):
    """Webhook → HTTP Request → Respond."""
    nodes = [
        tpl_webhook(webhook_path, "POST"),
        tpl_http_request(target_url, "POST"),
        tpl_respond_webhook()
    ]
    connections = {
        "Webhook": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]},
        "HTTP Request": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}
    }
    return await create_workflow(f"Webhook → HTTP ({webhook_path})", nodes, connections)

async def create_webhook_code(webhook_path="jod-code", js_code=None):
    """Webhook → Code Node → Respond."""
    if not js_code:
        js_code = """// Processa os dados recebidos
const items = $input.all();
return items.map(item => ({
  json: {
    ...item.json,
    processado: true,
    timestamp: new Date().toISOString()
  }
}));"""
    nodes = [
        tpl_webhook(webhook_path, "POST"),
        tpl_code(js_code),
        tpl_respond_webhook("={{ $json }}")
    ]
    connections = {
        "Webhook": {"main": [[{"node": "Code", "type": "main", "index": 0}]]},
        "Code": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}
    }
    return await create_workflow(f"Webhook → Code ({webhook_path})", nodes, connections)

async def create_schedule_http(cron="0 9 * * 1-5", url="https://httpbin.org/get"):
    """Schedule → HTTP Request."""
    nodes = [tpl_schedule(cron), tpl_http_request(url)]
    connections = {
        "Schedule Trigger": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]}
    }
    return await create_workflow(f"Schedule → HTTP ({url[:30]})", nodes, connections)

async def create_error_handler(notify_url="https://httpbin.org/post"):
    """Error Trigger → HTTP notify."""
    nodes = [
        tpl_error_trigger(),
        tpl_code("""// Formata o erro para notificação
const error = $input.first().json;
return [{json: {
  workflow: error.workflow?.name || 'unknown',
  error: error.execution?.error?.message || 'unknown error',
  timestamp: new Date().toISOString()
}}];"""),
        tpl_http_request(notify_url, "POST")
    ]
    connections = {
        "Error Trigger": {"main": [[{"node": "Code", "type": "main", "index": 0}]]},
        "Code": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]}
    }
    return await create_workflow("Error Handler — JOD_ROBO", nodes, connections)

async def create_manual_code(js_code=None, name="Manual + Code"):
    """Manual Trigger → Code (para testes rápidos)."""
    if not js_code:
        js_code = """// Workflow de teste
return [{json: {
  status: 'ok',
  message: 'Workflow executado com sucesso',
  timestamp: new Date().toISOString()
}}];"""
    nodes = [tpl_manual_trigger(), tpl_code(js_code)]
    connections = {
        "When clicking 'Test workflow'": {"main": [[{"node": "Code", "type": "main", "index": 0}]]}
    }
    return await create_workflow(name, nodes, connections)

# ─── ROTEAMENTO POR DESCRIÇÃO ────────────────────────────────────────────────────

async def create_from_description(description: str) -> dict:
    """Cria o workflow mais adequado baseado na descrição."""
    desc = description.lower()

    if "webhook" in desc and ("code" in desc or "javascript" in desc or "js" in desc):
        result = await create_webhook_code()
    elif "webhook" in desc and ("http" in desc or "api" in desc or "request" in desc):
        result = await create_webhook_http()
    elif "schedule" in desc or "agendado" in desc or "cron" in desc or "diario" in desc:
        result = await create_schedule_http()
    elif "erro" in desc or "error" in desc or "falha" in desc or "handler" in desc:
        result = await create_error_handler()
    elif "teste" in desc or "test" in desc or "manual" in desc:
        result = await create_manual_code()
    else:
        result = await create_manual_code(name=f"Workflow — {description[:40]}")

    wf_id = result.get("id")
    return {
        "id": wf_id,
        "name": result.get("name"),
        "url": f"{N8N_URL}/workflow/{wf_id}",
        "status": "created"
    }

if __name__ == "__main__":
    async def test():
        print("=== AGENTE N8N v2.0 ===\n")

        print("1. Listando workflows...")
        workflows = await list_workflows()
        print(f"   {len(workflows)} workflows encontrados")
        for w in workflows:
            print(f"   - [{w['id']}] {w['name']} (ativo: {w['active']})")

        print("\n2. Criando workflow webhook + code...")
        r = await create_webhook_code("teste-jod")
        print(f"   Criado: {r['name']} | ID: {r['id']}")

        print("\n3. Criando workflow schedule + http...")
        r2 = await create_schedule_http("0 8 * * 1-5", "https://httpbin.org/get")
        print(f"   Criado: {r2['name']} | ID: {r2['id']}")

        print(f"\n✅ Acesse em: {N8N_URL}")

    asyncio.run(test())
